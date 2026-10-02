"""
List and auto-detect PulseAudio / PipeWire monitor sources.

Linux-only. On other platforms these functions return empty results so
the caller falls back to whatever value the user has configured.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys

logger = logging.getLogger(__name__)


def list_monitor_sources() -> list[str]:
    """Return the names of every .monitor source, in pactl's order."""
    if sys.platform != "linux":
        return []
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


def default_monitor_source() -> str:
    """Pick a reasonable default monitor source.

    Preference order:
      1. analog-stereo.monitor — built-in laptop speakers
      2. any non-HDMI monitor  — external headphones, USB, etc.
      3. first available monitor
      4. empty string if none is present
    """
    sources = list_monitor_sources()
    if not sources:
        return ""

    for s in sources:
        if "analog-stereo.monitor" in s:
            return s

    for s in sources:
        if "hdmi" not in s.lower():
            return s

    return sources[0]