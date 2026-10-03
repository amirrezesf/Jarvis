"""
Post-transcription corrections.

Deterministic, code-level fixes for terms Whisper consistently
mishears on this specific audio distribution. Keep this list SHORT and
targeted. If it grows past ~30 entries, something else is wrong
(model choice, audio quality, or the term needs a hotwords entry).
"""

from __future__ import annotations

import re

# Order matters only for overlapping patterns; longest first.
_CORRECTIONS: list[tuple[str, str]] = [
    # Whisper consistently emits "زایه" for "ضایعه" on this audio.
    (r"\bزایه\b", "ضایعه"),
    # Spoken Persian numerals that come out wrong.
    (r"\bکود تعدیلی\b", "کد تعدیلی"),
    (r"\bچهارت\b", "چهار تا"),
]


def apply(text: str) -> str:
    """Return text with known corrections applied."""
    for pattern, replacement in _CORRECTIONS:
        text = re.sub(pattern, replacement, text)
    return text