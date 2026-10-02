"""
Audible alert for the listener.

Plays a short sound via paplay (PipeWire/PulseAudio) or aplay (ALSA).
Runs as a fire-and-forget subprocess so it never blocks the listener.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess

from jarvis import config

logger = logging.getLogger(__name__)


def _player_command(path: str) -> list[str] | None:
    """Pick the first available audio player for the given file."""
    if shutil.which("paplay"):
        return ["paplay", path]
    if shutil.which("aplay"):
        return ["aplay", "-q", path]
    return None


def play() -> None:
    """Play the configured alarm sound. Never raises."""
    if not config.ALARM_ENABLED:
        return

    path = config.ALARM_SOUND_PATH
    if not path or not os.path.exists(path):
        logger.warning("Alarm sound not found: %s", path)
        return

    cmd = _player_command(path)
    if cmd is None:
        logger.warning("No audio player found (install paplay or aplay)")
        return

    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as exc:
        logger.warning("Alarm playback failed: %s", exc)