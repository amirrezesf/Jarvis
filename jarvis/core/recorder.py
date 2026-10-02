"""
Session logging.

Writes:
    logs/sessions/<YYYY-MM-DD>.jsonl    one line per segment / turn

Audio is intentionally not persisted.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from jarvis import config
from jarvis.core.events import Utterance, Transcript

logger = logging.getLogger(__name__)


class SessionRecorder:
    """Append per-segment metadata to a daily JSONL file."""

    def __init__(self, sessions_dir: str | None = None) -> None:
        self.sessions_dir = Path(sessions_dir or config.SESSIONS_DIR)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._session_id: str | None = None

    # ------------------------------------------------------------------
    def start_session(self, mode: str = "assistant") -> str:
        """Mark the beginning of a new logical session. Returns the id.

        For listener mode, call once at startup and reuse the same id
        for every segment over the whole class.
        """
        now = datetime.now().astimezone()
        self._session_id = f"{now.strftime('%Y%m%d_%H%M%S')}_{mode}"
        logger.info("Session started: %s", self._session_id)
        return self._session_id

    # ------------------------------------------------------------------
    def log_turn(
        self,
        utt: Utterance,
        transcript: Transcript | None,
        reply: str | None,
        agent_seconds: float | None,
        agent_first_token_seconds: float | None = None,
        error: str | None = None,
        extra: dict | None = None,
    ) -> None:
        """Append one JSON line to today's session file."""
        now = datetime.now().astimezone()

        entry = {
            "ts": now.isoformat(timespec="milliseconds"),
            "session_id": self._session_id,
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
            "agent_first_token_seconds": (
                round(agent_first_token_seconds, 3)
                if agent_first_token_seconds is not None
                else None
            ),
            "error": error,
        }
        if extra:
            entry.update(extra)

        session_file = self.sessions_dir / f"{now.date().isoformat()}.jsonl"
        try:
            with session_file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.error("Failed to append to %s: %s", session_file, exc)