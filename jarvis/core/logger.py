"""
One-time root logger setup.

Call setup_logging() once at program start. Idempotent.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from jarvis import config

_configured = False


def setup_logging() -> None:
    """Configure the root logger with console + file handlers."""
    global _configured
    if _configured:
        return

    log_dir = Path(config.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)
    # Remove any handlers set up by a previous basicConfig() call.
    for h in list(root.handlers):
        root.removeHandler(h)

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = logging.FileHandler(
        log_dir / "jarvis.log", encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    _configured = True