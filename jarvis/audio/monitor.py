"""
List and auto-detect system-audio capture sources.

Linux: PipeWire / PulseAudio `.monitor` sources, listed via `pactl`.
Windows: WASAPI loopback devices, listed via the `soundcard` library.
macOS: not yet supported (returns empty).
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def list_monitor_sources() -> list[str]:
    """Return the names of every available capture source."""
    if sys.platform == "linux":
        return _linux_monitors()
    if sys.platform == "win32":
        return _windows_loopbacks()
    return []


def default_monitor_source() -> str:
    """Pick a reasonable default capture source."""
    if sys.platform == "win32":
        return _windows_default()
    return _linux_default()


# ---------------------------------------------------------------------------
# Linux — PipeWire / PulseAudio monitors
# ---------------------------------------------------------------------------
def _linux_monitors() -> list[str]:
    if not shutil.which("pactl"):
        logger.debug("pactl not found; no monitor sources available")
        return []
    try:
        proc = subprocess.run(
            ["pactl", "list", "short", "sources"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception as e:
        logger.warning("pactl failed: %s", e)
        return []
    if proc.returncode != 0:
        logger.warning("pactl returned %d", proc.returncode)
        return []

    out: list[str] = []
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        name = parts[1].strip()
        if name.endswith(".monitor"):
            out.append(name)
    return out


def _linux_default() -> str:
    sources = _linux_monitors()
    if not sources:
        return ""
    for s in sources:
        if "analog-stereo.monitor" in s:
            return s
    for s in sources:
        if "hdmi" not in s.lower():
            return s
    return sources[0]


# ---------------------------------------------------------------------------
# Windows — WASAPI loopback via soundcard
# ---------------------------------------------------------------------------
def _windows_loopbacks() -> list[str]:
    """Return the names of every speaker whose output can be captured."""
    try:
        import soundcard as sc
    except ImportError:
        logger.debug("soundcard not installed; no loopback devices")
        return []
    try:
        return [s.name for s in sc.all_speakers()]
    except Exception as e:
        logger.warning("soundcard all_speakers failed: %s", e)
        return []


def _windows_default() -> str:
    try:
        import soundcard as sc
        return sc.default_speaker().name
    except Exception as e:
        logger.warning("soundcard default_speaker failed: %s", e)
        return ""