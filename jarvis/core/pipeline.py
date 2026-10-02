"""
Listener pipeline.

Ties together extraction, trigger detection, state, and decision-making.

One pipeline instance per session. Feed it transcript segments as they
arrive; it returns zero or more Decision objects.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime

from jarvis import config
from jarvis.core.events import Decision, InstructionRecord, TriggerEvent
from jarvis.core.extraction import Extractor, ExtractionError
from jarvis.core.state import InstructionState
from jarvis.core.triggers import (
    NameDetector,
    _score_variant,
    normalize as _norm,
)

logger = logging.getLogger(__name__)


class ListenerPipeline:
    def __init__(
        self,
        extractor: Extractor | None = None,
        detector: NameDetector | None = None,
        state: InstructionState | None = None,
    ) -> None:
        self.extractor = extractor or Extractor()
        self.detector = detector or NameDetector()
        self.state = state or InstructionState()
        self._window: list[str] = []

    # ------------------------------------------------------------------
    def feed(self, segment: str) -> list[Decision]:
        """Process one transcript segment. Returns any decisions produced."""
        t_start = time.perf_counter()

        decisions: list[Decision] = []

        self._window.append(segment)
        if len(self._window) > config.EXTRACTION_WINDOW_SEGMENTS:
            self._window = self._window[-config.EXTRACTION_WINDOW_SEGMENTS:]

        # 1. Skip extraction if the segment is a bare name call.
        name_only = self._is_name_only(segment)
        t_extract0 = time.perf_counter()
        if name_only:
            records = []
            extract_seconds = 0.0
        else:
            try:
                records = self.extractor.extract(self._window)
            except ExtractionError as exc:
                logger.error("Extraction failed: %s", exc)
                records = []
            extract_seconds = time.perf_counter() - t_extract0

        # 2. Route records.
        immediate_fired = False
        for rec in records:
            if rec.action == "none":
                continue
            if rec.trigger_type == "immediate":
                decisions.append(self._decision_from_immediate(rec))
                immediate_fired = True
            else:
                self.state.add(rec)

        # 3. Trigger scan.
        t_trigger0 = time.perf_counter()
        events = self.detector.scan(segment)
        if not immediate_fired:
            for ev in events:
                if not ev.fired:
                    continue
                if ev.type == "name_called":
                    matched = self.state.pop_matching_name_trigger()
                    if matched is not None:
                        decisions.append(self._decision_from_match(ev, matched))
                    else:
                        logger.info(
                            "Name mentioned, no pending instruction: %r",
                            ev.evidence,
                        )
        trigger_seconds = time.perf_counter() - t_trigger0

        # 4. Expire.
        self.state.expire()

        total_seconds = time.perf_counter() - t_start

        logger.info(
            "timing other=%.3fs extract=%.3fs trigger=%.3fs total=%.3fs "
            "name_only=%s decisions=%d",
            total_seconds - extract_seconds - trigger_seconds,
            extract_seconds,
            trigger_seconds,
            total_seconds,
            name_only,
            len(decisions),
        )

        return decisions

    # ------------------------------------------------------------------
    def _is_name_only(self, segment: str) -> bool:
        """True if stripping a name match leaves nothing meaningful.

        Uses the same fuzzy matcher as the trigger detector, so a
        mis-transcribed first name like 'امیرزا' still counts as a name.
        """
        text = _norm(segment)
        if not text:
            return False

        # Find the longest name match at or above candidate threshold.
        best: tuple[int, int] | None = None
        for variant in self.detector.variants:
            score, _evidence, start, end = _score_variant(variant, text)
            if score < self.detector.candidate_threshold:
                continue
            if best is None or (end - start) > (best[1] - best[0]):
                best = (start, end)

        if best is None:
            return False

        start, end = best
        remaining = text[:start] + " " + text[end:]

        # Strip punctuation and common filler.
        remaining = re.sub(r"[؟?!.,،\s]+", " ", remaining)
        for filler in ("بله", "بلی", "آره", "لطفاً", "لطفا", "خب"):
            remaining = remaining.replace(filler, " ")
        remaining = remaining.strip()

        result = len(remaining) < 3
        logger.info(
            "name_only check: in=%r remaining=%r result=%s",
            text, remaining, result,
        )
        return result


    # ------------------------------------------------------------------
    def _decision_from_immediate(self, rec: InstructionRecord) -> Decision:
        return Decision(
            ts=datetime.now(),
            action=rec.action,
            args=dict(rec.args),
            trigger_evidence="",
            trigger_score=0.0,
            instruction_source=rec.source_text,
            instruction_scope=rec.scope,
            instruction_confidence=rec.confidence,
            reasoning=f"immediate: {rec.reasoning}",
            context_summary=rec.context_summary,
        )

    def _decision_from_match(
        self, ev: TriggerEvent, rec: InstructionRecord
    ) -> Decision:
        return Decision(
            ts=datetime.now(),
            action=rec.action,
            args=dict(rec.args),
            trigger_evidence=ev.evidence,
            trigger_score=ev.score,
            instruction_source=rec.source_text,
            instruction_scope=rec.scope,
            instruction_confidence=rec.confidence,
            reasoning=(
                f"matched {ev.type}@{ev.score:.0f} -> "
                f"{rec.trigger_type}: {rec.reasoning}"
            ),
            context_summary=rec.context_summary,
        )
