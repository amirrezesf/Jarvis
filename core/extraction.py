"""
LLM layer: instruction extraction.

Sends a rolling window of transcript segments to a model via 9Router
and parses the response into InstructionRecord objects.

Non-streaming: extraction needs the full JSON before it can be
validated and used. One retry on malformed output or transient errors.
"""

from __future__ import annotations

import json
import logging
import re

import requests

import config
from core.events import InstructionRecord
from core.prompts import (
    INSTRUCTION_EXTRACTION_SYSTEM,
    INSTRUCTION_EXTRACTION_USER,
)

logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    """Raised when the LLM call fails irrecoverably."""


_VALID_TRIGGERS = {"name_called", "keyword", "immediate", "none"}
_VALID_ACTIONS = {"type_number", "send_chat", "notify_me", "none"}
_VALID_SCOPES = {"personal", "broadcast"}


class Extractor:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        self.base_url = (base_url or config.NINEROUTER_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else config.NINEROUTER_KEY
        self.model = model or config.EXTRACTION_MODEL
        self.timeout = timeout if timeout is not None else config.EXTRACTION_TIMEOUT
        self.max_retries = (
            max_retries if max_retries is not None else config.EXTRACTION_MAX_RETRIES
        )

        self._session = requests.Session()
        if self.api_key:
            self._session.headers.update(
                {"Authorization": f"Bearer {self.api_key}"}
            )
        self._session.headers.update({"Content-Type": "application/json"})

    # ------------------------------------------------------------------
    def extract(self, segments: list[str]) -> list[InstructionRecord]:
        """Extract instructions from the last segment, using the rest as context.

        Returns [] on no instruction or unusable output.
        Raises ExtractionError only if every attempt failed at the HTTP level.
        """
        if not segments:
            return []

        window = segments[-config.EXTRACTION_WINDOW_SEGMENTS:]
        latest = window[-1]
        context = "\n".join(f"- {s}" for s in window[:-1]) or "(none)"

        user_msg = INSTRUCTION_EXTRACTION_USER.format(
            context=context, latest=latest,
        )

        last_error: Exception | None = None
        attempts = self.max_retries + 1

        for attempt in range(1, attempts + 1):
            try:
                raw = self._call_model(user_msg)
            except ExtractionError as exc:
                last_error = exc
                if attempt < attempts:
                    logger.warning(
                        "Extraction attempt %d/%d failed (%s); retrying",
                        attempt, attempts, exc,
                    )
                    continue
                raise

            records = self._parse(raw, source_text=latest)
            if records is not None:
                # Filter low-confidence records.
                return [
                    r for r in records
                    if r.confidence >= config.EXTRACTION_CONFIDENCE_MIN
                ]

            # Parse failed (returned None). Retry once.
            last_error = ExtractionError("Malformed JSON from extractor")
            logger.warning(
                "Extraction attempt %d/%d parse failed; raw=%r",
                attempt, attempts, raw[:200],
            )

        # All attempts failed at parse level.
        if last_error is not None:
            logger.error("Extraction gave up: %s", last_error)
        return []

    # ------------------------------------------------------------------
    def _call_model(self, user_msg: str) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": INSTRUCTION_EXTRACTION_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            "stream": False,
            "response_format": {"type": "json_object"},
        }

        logger.debug("Extraction POST  model=%s", self.model)

        try:
            resp = self._session.post(url, json=payload, timeout=self.timeout)
        except requests.RequestException as exc:
            raise ExtractionError(f"9Router call failed: {exc}") from exc

        if resp.status_code != 200:
            raise ExtractionError(
                f"9Router HTTP {resp.status_code}: {resp.text[:300]}"
            )

        try:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise ExtractionError(
                f"Unexpected response shape: {resp.text[:300]}"
            ) from exc

    # ------------------------------------------------------------------
    def _parse(
        self, raw: str, source_text: str
    ) -> list[InstructionRecord] | None:
        """Parse raw model output. Returns None if JSON is unrecoverable."""
        payload = _extract_json(raw)
        if payload is None:
            return None

        items = payload.get("instructions")
        if not isinstance(items, list):
            return None

        records: list[InstructionRecord] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            trigger = item.get("trigger_type")
            action = item.get("action")
            scope = item.get("scope")
            if trigger not in _VALID_TRIGGERS:
                logger.warning("Skipping bad trigger_type: %r", trigger)
                continue
            if action not in _VALID_ACTIONS:
                logger.warning("Skipping bad action: %r", action)
                continue
            if scope not in _VALID_SCOPES:
                logger.warning("Skipping bad scope: %r", scope)
                continue

            args = item.get("args")
            if not isinstance(args, dict):
                args = {}

            try:
                confidence = float(item.get("confidence", 0.0))
            except (TypeError, ValueError):
                confidence = 0.0
            confidence = max(0.0, min(1.0, confidence))

            summary = _truncate_words(
                str(item.get("context_summary", "")),
                config.EXTRACTION_CONTEXT_MAX_WORDS,
            )

            records.append(
                InstructionRecord(
                    trigger_type=trigger,
                    action=action,
                    args=args,
                    scope=scope,
                    confidence=confidence,
                    source_text=source_text,
                    context_summary=summary,
                    reasoning=str(item.get("reasoning", ""))[:200],
                )
            )
        return records


# ---------------------------------------------------------------------------
# JSON extraction helpers
# ---------------------------------------------------------------------------
def _extract_json(raw: str) -> dict | None:
    """Best-effort parse: raw JSON, fenced JSON, or first {...} block."""
    raw = raw.strip()

    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fenced:
        try:
            obj = json.loads(fenced.group(1))
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            pass

    brace = re.search(r"\{.*\}", raw, re.DOTALL)
    if brace:
        try:
            obj = json.loads(brace.group(0))
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            pass

    return None

def _truncate_words(text: str, max_words: int) -> str:
    """Trim text to at most max_words whitespace-separated words."""
    text = text.strip()
    if not text or max_words <= 0:
        return text
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "…"