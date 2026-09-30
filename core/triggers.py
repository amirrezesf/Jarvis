"""
Trigger detection.

Deterministic, code-only detection of events in the transcript stream.
First release handles name detection only.

Policy:
- Precision over recall: bias toward not firing.
- Log every candidate, including rejected ones.
- Attach evidence (score, matched span, context) to every event.
- Testable offline against a saved transcript file.

Stateful: the detector keeps a short rolling buffer of recent segments
so a name split across a VAD boundary is still caught. One detector
instance is meant to be used for the whole session — do not recreate
it per segment.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from rapidfuzz import fuzz

import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Persian text normalization
# ---------------------------------------------------------------------------
_NORMALIZE_MAP = {
    "\u064a": "\u06cc",  # Arabic ي  -> Persian ی
    "\u0643": "\u06a9",  # Arabic ك  -> Persian ک
    "\u0629": "\u0647",  # Arabic ة  -> Persian ه
    "\u06c0": "\u0647",  # Arabic ۀ  -> Persian ه
    "\u200c": " ",       # ZWNJ      -> space
    "\u200f": "",        # RTL mark
    "\u200e": "",        # LTR mark
}


def normalize(text: str) -> str:
    """Normalize Persian text for fuzzy matching."""
    for src, dst in _NORMALIZE_MAP.items():
        text = text.replace(src, dst)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------
@dataclass
class TriggerEvent:
    type: str               # e.g. "name_called"
    matched_variant: str    # the config variant that matched
    evidence: str           # the span in the transcript that matched
    score: float            # 0..100
    context: str            # the full buffered text at match time
    fired: bool             # True if score >= threshold, else candidate only


# ---------------------------------------------------------------------------
# Name detector
# ---------------------------------------------------------------------------
class NameDetector:
    """Detect the user's name in a rolling window of transcript segments."""

    def __init__(
        self,
        variants: list[str] | None = None,
        threshold: int | None = None,
        candidate_threshold: int | None = None,
        min_length: int | None = None,
        buffer_segments: int | None = None,
    ) -> None:
        raw_variants = variants if variants is not None else config.NAME_VARIANTS
        self.variants = [normalize(v) for v in raw_variants if v]
        self.threshold = (
            threshold if threshold is not None else config.NAME_MATCH_THRESHOLD
        )
        self.candidate_threshold = (
            candidate_threshold
            if candidate_threshold is not None
            else config.NAME_MATCH_CANDIDATE_THRESHOLD
        )
        self.min_length = (
            min_length if min_length is not None else config.NAME_MATCH_MIN_LENGTH
        )
        self.buffer_segments = (
            buffer_segments
            if buffer_segments is not None
            else config.NAME_BUFFER_SEGMENTS
        )

        self._buffer: list[str] = []

    # ------------------------------------------------------------------
    def scan(self, segment: str, return_all: bool = False) -> list[TriggerEvent]:
        """Scan a new segment, using recent history as context.

        Fires only if the matched evidence reaches into the newest
        segment. This prevents both split-name misses (name reassembled
        across the buffer) and repeated fires on stale text.
        """
        if not segment or not segment.strip():
            return []

        self._buffer.append(segment.strip())
        if len(self._buffer) > self.buffer_segments:
            self._buffer = self._buffer[-self.buffer_segments:]

        combined = normalize(" ".join(self._buffer))

        # Offset where the newest segment begins in the combined buffer.
        if len(self._buffer) > 1:
            prefix = normalize(" ".join(self._buffer[:-1]))
            newest_start = len(prefix) + 1 if prefix else 0
        else:
            newest_start = 0

        candidates: list[TriggerEvent] = []
        for variant in self.variants:
            if len(variant) < self.min_length:
                continue
            score, evidence, start, end = _score_variant(variant, combined)
            if score < self.candidate_threshold:
                continue
            if not _is_token_boundary(combined, start, end):
                continue
            # Skip matches that live entirely in older context.
            if end <= newest_start:
                continue
            candidates.append(
                TriggerEvent(
                    type="name_called",
                    matched_variant=variant,
                    evidence=evidence,
                    score=float(score),
                    context=combined,
                    fired=score >= self.threshold,
                )
            )

        if not candidates:
            return []
        candidates.sort(key=lambda e: e.score, reverse=True)
        return candidates if return_all else candidates[:1]
# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------
def _score_variant(variant: str, text: str) -> tuple[float, str, int, int]:
    """Return (score, matched_span, start, end) for variant against text."""
    try:
        result = fuzz.partial_ratio_alignment(variant, text)
        if result is not None:
            span = text[result.dest_start:result.dest_end]
            return (
                float(result.score),
                span,
                result.dest_start,
                result.dest_end,
            )
    except (AttributeError, TypeError):
        pass

    score = float(fuzz.partial_ratio(variant, text))
    return score, variant, 0, len(text)


def _is_token_boundary(text: str, start: int, end: int) -> bool:
    """True if the matched span starts and ends at word boundaries."""
    before = text[start - 1] if start > 0 else " "
    after = text[end] if end < len(text) else " "
    return (before.isspace() or not before.isalnum()) and (
        after.isspace() or not after.isalnum()
    )