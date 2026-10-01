"""
Listener pipeline.

Ties together extraction, trigger detection, state, and decision-making.

One pipeline instance per session. Feed it transcript segments as they
arrive; it returns zero or more Decision objects.
"""

from __future__ import annotations

import logging
from datetime import datetime

import config
from core.events import Decision, InstructionRecord, TriggerEvent
from core.extraction import Extractor, ExtractionError
from core.state import InstructionState
from core.triggers import NameDetector

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
        decisions: list[Decision] = []

        self._window.append(segment)
        if len(self._window) > config.EXTRACTION_WINDOW_SEGMENTS:
            self._window = self._window[-config.EXTRACTION_WINDOW_SEGMENTS:]

        # 1. Extract instructions from the window (latest = current).
        if _is_name_only(segment, self.detector.variants):
            logger.debug("Name-only segment; skipping extraction")
            records = []
        else:
            try:
                records = self.extractor.extract(self._window)
            except ExtractionError as exc:
                logger.error("Extraction failed: %s", exc)
                records = []

        # 2. Route each record.
        immediate_fired = False
        for rec in records:
            if rec.action == "none":
                continue
            if rec.trigger_type == "immediate":
                decisions.append(self._decision_from_immediate(rec))
                immediate_fired = True
            else:
                self.state.add(rec)

        # 3. Scan for triggers.
        #    Always call scan() so the detector's rolling buffer stays
        #    consistent, but IGNORE its events if an immediate instruction
        #    already fired on this segment. A segment that both addresses
        #    the user and contains an immediate action is a direct address;
        #    pending rules do not apply to it.
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
                        logger.debug(
                            "Name mentioned, no pending instruction: %r",
                            ev.evidence,
                        )

        # 4. Expire stale state.
        self.state.expire()

        return decisions

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

import re

from core.triggers import normalize as _norm


def _is_name_only(segment: str, variants: list[str]) -> bool:
    """True if the segment contains nothing but a name and short filler.

    Deterministic guard against the extractor treating a roll-call name
    call as a standalone instruction or question.
    """
    text = _norm(segment)
    for variant in variants:
        text = text.replace(variant, " ")
    # Strip punctuation, filler, and whitespace.
    text = re.sub(r"[؟?!.,،\s]+", " ", text)
    for filler in ("بله", "بلی", "آره", "بله؟"):
        text = text.replace(filler, " ")
    text = text.strip()
    return len(text) < 3