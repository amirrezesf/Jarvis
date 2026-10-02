"""
Runtime config loader.

Reads ~/.jarvis/config.json and merges it on top of jarvis/config.py.
The JSON file is the source of truth for anything user-specific
(model paths, API keys, device selection). config.py holds the
defaults that ship with the code.

On first import the file is created from the current config.py values.

Path rules for values in config.json:
    - Absolute paths are used as-is
    - "~/..." is expanded to the user's home directory
    - Relative paths are resolved against ~/.jarvis/ (not cwd)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

JARVIS_DIR = Path.home() / ".jarvis"
CONFIG_FILE = JARVIS_DIR / "config.json"
MODELS_DIR = JARVIS_DIR / "models"
LOGS_DIR = JARVIS_DIR / "logs"

_PATH_FIELDS = {"WHISPER_MODEL", "ALARM_SOUND_PATH"}

_MIGRATED_FIELDS = [
    "WHISPER_MODEL",
    "DEVICE",
    "COMPUTE_TYPE",
    "LANGUAGE",
    "LOOPBACK_DEVICE",
    "ALARM_ENABLED",
    "ALARM_SOUND_PATH",
    "EXTRACTION_BACKEND",
    "EXTRACTION_MODEL",
    "LOCAL_LLM_URL",
    "LOCAL_EXTRACTION_MODEL",
    "NINEROUTER_URL",
    "NINEROUTER_KEY",
    "NINEROUTER_COMBO_NAME",
    "ACTION_EXECUTION_ENABLED",
    "ACTION_DRY_RUN",
    "ACTION_REQUIRE_CONFIRM",
    "ACTION_DISABLED",
]

def _resolve_path(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return value
    if value.lower() in ("default", "package"):
        return value
    # Only treat as a path if it *looks* like one. Hugging Face model
    # names like "large-v3-turbo" or "Systran/faster-whisper-large-v3"
    # must be left alone — expanding them to ~/.jarvis/<name> breaks
    # faster-whisper's own repo-id resolution.
    looks_like_path = (
        value.startswith("/")
        or value.startswith("~")
        or value.startswith("./")
        or value.startswith("../")
        or value.startswith(".\\")
    )
    if not looks_like_path:
        return value
    p = Path(value).expanduser()
    if not p.is_absolute():
        p = JARVIS_DIR / p
    return str(p)

def _ensure_dirs() -> None:
    JARVIS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

def _migrate(defaults: dict) -> dict:
    out = {k: defaults[k] for k in _MIGRATED_FIELDS if k in defaults}

    # Auto-detect the monitor source if the default is empty or missing.
    if not out.get("LOOPBACK_DEVICE"):
        try:
            from jarvis.audio.monitor import default_monitor_source
            detected = default_monitor_source()
            if detected:
                out["LOOPBACK_DEVICE"] = detected
                logger.info("Auto-detected monitor source: %s", detected)
            else:
                logger.warning(
                    "No monitor source detected; set LOOPBACK_DEVICE "
                    "in %s before starting the listener",
                    CONFIG_FILE,
                )
        except Exception as e:
            logger.warning("Monitor auto-detect failed: %s", e)

    try:
        CONFIG_FILE.write_text(
            json.dumps(out, ensure_ascii=False, indent=4) + "\n",
            encoding="utf-8",
        )
        logger.info("Created %s with %d defaults", CONFIG_FILE, len(out))
    except Exception as exc:
        logger.warning("Could not write %s: %s", CONFIG_FILE, exc)
    return out

def load(defaults: dict) -> dict:
    _ensure_dirs()

    if not CONFIG_FILE.is_file():
        return _migrate(defaults)

    try:
        raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Could not parse %s: %s — using defaults",
                       CONFIG_FILE, exc)
        return {}

    if not isinstance(raw, dict):
        logger.warning("%s is not a JSON object — using defaults", CONFIG_FILE)
        return {}

    overrides: dict = {}
    for key, value in raw.items():
        if key not in defaults:
            logger.warning("Ignoring unknown config key %r", key)
            continue
        if key in _PATH_FIELDS:
            value = _resolve_path(value)
        overrides[key] = value
    return overrides


def apply_overrides(namespace: dict) -> None:
    overrides = load(namespace)
    for key, value in overrides.items():
        namespace[key] = value

def reload_into(namespace: dict) -> None:
    """Re-read config.json and apply the values into a module namespace.

    Used by the GUI after saving, so the running process picks up the
    new values without a restart. The active Listener uses the config
    module at every call, so the change takes effect on the next
    segment — no thread restart required.
    """
    overrides = load(namespace)
    for key, value in overrides.items():
        namespace[key] = value