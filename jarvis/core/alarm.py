"""
Audible alert for the listener.

Plays a short sound via paplay (PipeWire/PulseAudio) or aplay (ALSA).
Runs as a fire-and-forget subprocess so it never blocks the listener.

By default the sound is the one shipped with the package. Set
config.ALARM_SOUND_PATH to an absolute path to override it.
"""

from __future__ import annotations

import functools
import logging
import os
import shutil
import subprocess
from importlib import resources
from pathlib import Path

from jarvis import config


logger = logging.getLogger(__name__)

_PACKAGE_ALARM_NAME = "alarm.mp3"
_OVERRIDE_SENTINELS = {"", "default", "package"}


# ---------------------------------------------------------------------------
# Packaged alarm resolution
# ---------------------------------------------------------------------------
@functools.lru_cache(maxsize=1)
def _package_alarm_path() -> str | None:
    """Return a stable filesystem path to the packaged alarm sound.

    Handles three install shapes:
      - editable / source checkout: the file is right there on disk
      - wheel install:               the file is in site-packages/jarvis/assets/
      - zipimport:                   the file is inside a zip; copy it out

    Cached because resolving costs a syscall at minimum and a copy in the
    zipimport case.
    """
    try:
        ref = resources.files("jarvis.assets").joinpath(_PACKAGE_ALARM_NAME)
    except (ModuleNotFoundError, TypeError) as exc:
        logger.warning("Packaged alarm asset missing: %s", exc)
        return None

    # Fast path: a real file already on disk.
    try:
        p = Path(str(ref))
        if p.is_file():
            return str(p)
    except (OSError, TypeError):
        pass

    # Slow path: extract once to a stable location.
    try:
        with resources.as_file(ref) as p:
            stable = Path.home() / ".jarvis" / _PACKAGE_ALARM_NAME
            stable.parent.mkdir(parents=True, exist_ok=True)
            if not stable.is_file() or stable.stat().st_size == 0:
                shutil.copy(p, stable)
            return str(stable)
    except Exception as exc:
        logger.warning("Could not extract packaged alarm: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Player selection
# ---------------------------------------------------------------------------
def _player_command(path: str) -> list[str] | None:
    """Pick the first available audio player for the given file."""
    if shutil.which("paplay"):
        return ["paplay", path]
    if shutil.which("aplay"):
        return ["aplay", "-q", path]
    return None


# ---------------------------------------------------------------------------
def play() -> None:
    """Play the configured alarm sound. Never raises."""
    if not config.ALARM_ENABLED:
        return

    configured = (config.ALARM_SOUND_PATH or "").strip()
    if configured.lower() in _OVERRIDE_SENTINELS:
        path = _package_alarm_path()
        if path is None:
            logger.warning("No packaged alarm available")
            return
    else:
        path = os.path.expanduser(configured)
        if not os.path.isfile(path):
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