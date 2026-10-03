"""
Preload CUDA libraries from pip-installed NVIDIA wheels.

SkyroomBot (and any caller that isn't a shell with LD_LIBRARY_PATH
exported) can't rely on the dynamic linker finding libcublas / libcudnn
by name. Preloading them explicitly with RTLD_GLOBAL makes subsequent
dlopen() calls from ctranslate2 resolve to the already-loaded copies.

Linux only. On Windows the equivalent libraries are found via PATH and
this module is a no-op.
"""

from __future__ import annotations

import ctypes
import glob
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_LIB_PATTERNS = (
    "libcublas.so.*",
    "libcublasLt.so.*",
    "libcudnn.so.*",
)

_preloaded = False


def _candidate_dirs() -> list[Path]:
    """Directories that might contain the CUDA shared objects."""
    dirs: list[Path] = []

    # Preferred: the pip-installed nvidia-* wheels.
    try:
        import nvidia.cublas.lib as _cublas
        f = getattr(_cublas, "__file__", None)
        if f:
            dirs.append(Path(f).parent)
    except Exception:
        pass
    try:
        import nvidia.cudnn.lib as _cudnn
        f = getattr(_cudnn, "__file__", None)
        if f:
            dirs.append(Path(f).parent)
    except Exception:
        pass
    # Fallback: scan every site-packages entry for nvidia/<pkg>/lib.
    for base in sys.path:
        nvidia_dir = Path(base) / "nvidia"
        if not nvidia_dir.is_dir():
            continue
        for sub in ("cublas", "cudnn"):
            lib_dir = nvidia_dir / sub / "lib"
            if lib_dir.is_dir() and lib_dir not in dirs:
                dirs.append(lib_dir)

    return dirs


def preload() -> None:
    """Load the CUDA shared objects into the process. Idempotent, never raises."""
    global _preloaded
    if _preloaded:
        return
    _preloaded = True

    if sys.platform != "linux":
        return

    loaded = 0
    for d in _candidate_dirs():
        for pattern in _LIB_PATTERNS:
            for lib_path in sorted(glob.glob(str(d / pattern))):
                try:
                    ctypes.CDLL(lib_path, mode=ctypes.RTLD_GLOBAL)
                    logger.info("Preloaded %s", lib_path)
                    loaded += 1
                except OSError as e:
                    logger.warning("Could not preload %s: %s", lib_path, e)

    if loaded == 0:
        logger.info(
            "No pip-installed CUDA libraries found; Whisper will fall back "
            "to CPU if no other CUDA runtime is available.",
        )