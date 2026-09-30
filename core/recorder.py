"""
Session logging.

Writes:
    logs/sessions/<YYYY-MM-DD>.jsonl    one line per completed turn

Audio is intentionally not persisted. Only the transcript, the reply,
and timing metadata are written, which is enough to audit turns and
to tune transcription options against the text.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import config
from core.events import Utterance, Transcript

logger = logging.getLogger(__name__)


class SessionRecorder:
    """Append per-turn metadata to a daily JSONL file."""

    def __init__(self, sessions_dir: str | None = None) -> None:
        self.sessions_dir = Path(sessions_dir or config.SESSIONS_DIR)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def log_turn(
        self,
        utt: Utterance,
        transcript: Transcript | None,
        reply: str | None,
        agent_seconds: float | None,
        error: str | None = None,
    ) -> None:
        """Append one JSON line to today's session file."""
        now = datetime.now().astimezone()

        entry = {
            "ts": now.isoformat(timespec="milliseconds"),
            "source": utt.source,
            "audio_seconds": round(len(utt.audio) / config.SAMPLE_RATE, 3),
            "transcript": transcript.text if transcript else None,
            "transcribe_seconds": (
                round(transcript.seconds, 3) if transcript else None
            ),
            "agent_reply": reply,
            "agent_seconds": (
                round(agent_seconds, 3) if agent_seconds is not None else None
            ),
            "error": error,
        }

        session_file = self.sessions_dir / f"{now.date().isoformat()}.jsonl"
        try:
            with session_file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.error("Failed to append to %s: %s", session_file, exc)