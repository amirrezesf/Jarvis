"""
Agent wrapper for 9Router.

Talks to a local 9Router gateway's OpenAI-compatible API.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Iterator

import requests

from jarvis import config

logger = logging.getLogger(__name__)


class AgentError(Exception):
    """Base exception for agent errors."""


class AgentConnectionError(AgentError):
    """Raised when the 9Router gateway cannot be reached."""


class AgentTimeoutError(AgentError):
    """Raised when the 9Router request exceeds the configured timeout."""


class Agent:
    """Thin wrapper around a 9Router gateway's HTTP API.

    Streaming is the default. ``ask()`` is kept as a convenience for
    callers that just want the full string in one go.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        retry_delay: float | None = None,
    ) -> None:
        self.base_url = (base_url or config.NINEROUTER_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else config.NINEROUTER_KEY
        self.model = model or config.NINEROUTER_COMBO_NAME
        self.timeout = timeout if timeout is not None else config.NINEROUTER_TIMEOUT
        self.max_retries = (
            config.NINEROUTER_MAX_RETRIES
            if max_retries is None
            else max_retries
        )
        self.retry_delay = (
            config.NINEROUTER_RETRY_DELAY
            if retry_delay is None
            else retry_delay
        )

        self._session = requests.Session()
        if self.api_key:
            self._session.headers.update(
                {"Authorization": f"Bearer {self.api_key}"}
            )
        self._session.headers.update({"Content-Type": "application/json"})

    # ------------------------------------------------------------------
    def ask(self, text: str) -> str:
        """Non-streaming convenience. Returns the full reply as one string."""
        return "".join(self.ask_stream(text))

    # ------------------------------------------------------------------
    def ask_stream(self, text: str) -> Iterator[str]:
        """Yield reply text chunks, retrying once on transient failures.

        A retry is only attempted if the previous attempt failed *before*
        yielding any content. Once a token has been delivered to the
        caller we cannot un-yield it, so mid-stream failures propagate.
        """
        last_error: Exception | None = None
        attempts = self.max_retries + 1

        for attempt in range(1, attempts + 1):
            yielded_any = False
            try:
                for chunk in self._ask_stream_once(text):
                    yielded_any = True
                    yield chunk
                return
            except (AgentConnectionError, AgentTimeoutError, AgentError) as exc:
                last_error = exc
                if yielded_any:
                    # Already delivered tokens to the caller; cannot retry.
                    raise
                if attempt < attempts:
                    logger.warning(
                        "Agent attempt %d/%d failed (%s); retrying in %.1fs",
                        attempt, attempts, exc, self.retry_delay,
                    )
                    time.sleep(self.retry_delay)
                    continue
                raise

        if last_error is not None:  # unreachable, but keeps type checkers happy
            raise last_error

    # ------------------------------------------------------------------
    def _ask_stream_once(self, text: str) -> Iterator[str]:
        """One streaming attempt. Raises on any error."""
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": text}],
            "stream": True,
        }

        logger.debug(
            "POST %s (stream)  model=%s  chars=%d",
            url, self.model, len(text),
        )

        try:
            resp = self._session.post(
                url, json=payload, timeout=self.timeout, stream=True
            )
        except requests.ConnectionError as exc:
            raise AgentConnectionError(
                f"Cannot reach 9Router at {self.base_url}. "
                "Is `9router` running? "
                f"({exc})"
            ) from exc
        except requests.Timeout as exc:
            raise AgentTimeoutError(
                f"9Router request timed out after {self.timeout:.0f}s."
            ) from exc

        with resp:
            if resp.status_code == 401:
                raise AgentError(
                    "9Router rejected the API key (HTTP 401). "
                    "Check NINEROUTER_KEY in config.py."
                )
            if resp.status_code != 200:
                raise AgentError(
                    f"9Router returned HTTP {resp.status_code}: "
                    f"{resp.text[:500]}"
                )

            buffer = ""
            got_content = False
            error_event: str | None = None

            try:
                for raw in resp.iter_content(chunk_size=1024):
                    if not raw:
                        continue
                    # Explicit UTF-8: providers omit charset, requests
                    # then guesses latin-1 and mangles Persian.
                    buffer += raw.decode("utf-8", errors="replace")

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.rstrip("\r")
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            if error_event and not got_content:
                                raise AgentError(error_event)
                            if not got_content:
                                logger.warning(
                                    "9Router stream finished with no content "
                                    "(model=%s). The combo may have hit a "
                                    "reasoning-only or failing model.",
                                    self.model,
                                )
                            return
                        try:
                            obj = json.loads(data)
                        except json.JSONDecodeError:
                            logger.warning("Bad SSE chunk: %r", line[:200])
                            continue

                        # 9Router wraps upstream failures as an error
                        # event inside an otherwise HTTP 200 stream.
                        if "error" in obj:
                            err = obj["error"]
                            msg = (
                                err.get("message")
                                if isinstance(err, dict)
                                else str(err)
                            )
                            logger.warning("9Router error event: %s", msg)
                            error_event = f"9Router upstream error: {msg}"
                            # Keep draining until [DONE] so the connection
                            # closes cleanly, then raise above.
                            continue

                        choices = obj.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        content = delta.get("content")
                        if content:
                            got_content = True
                            yield content

            except requests.Timeout as exc:
                raise AgentTimeoutError(
                    f"9Router stream stalled for {self.timeout:.0f}s."
                ) from exc
            except requests.ConnectionError as exc:
                raise AgentConnectionError(
                    f"9Router stream dropped: {exc}"
                ) from exc

            if error_event and not got_content:
                raise AgentError(error_event)