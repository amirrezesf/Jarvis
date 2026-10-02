"""
Silero VAD, ONNX Runtime backend.

Self-contained: no torch. Loads the ONNX model directly, manages the
LSTM state and the 64-sample context window that the model expects.
Bit-exact with the PyTorch silero model; up to 5x faster on CPU and
~200 MB smaller in memory.

The model file is shipped with the package at jarvis/assets/silero_vad.onnx.
"""

from __future__ import annotations

import logging
from importlib import resources
from pathlib import Path

import numpy as np
import onnxruntime as ort

logger = logging.getLogger(__name__)

# Silero VAD v5 contract for 16 kHz input.
_CHUNK_SAMPLES = 512
_CONTEXT_SAMPLES = 64
_STATE_SHAPE = (2, 1, 128)

_MODEL_NAME = "silero_vad.onnx"


def _resolve_model_path() -> str:
    """Return a filesystem path to the packaged ONNX model."""
    try:
        ref = resources.files("jarvis.assets").joinpath(_MODEL_NAME)
    except (ModuleNotFoundError, TypeError) as exc:
        raise RuntimeError(
            f"jarvis.assets is not importable: {exc}"
        ) from exc

    p = Path(str(ref))
    if p.is_file():
        return str(p)

    # Zipimport case — extract once to a stable location.
    try:
        with resources.as_file(ref) as src:
            stable = Path.home() / ".jarvis" / _MODEL_NAME
            stable.parent.mkdir(parents=True, exist_ok=True)
            if not stable.is_file() or stable.stat().st_size == 0:
                import shutil
                shutil.copy(src, stable)
            return str(stable)
    except Exception as exc:
        raise RuntimeError(
            f"Could not resolve packaged {_MODEL_NAME}: {exc}"
        ) from exc


class SileroVAD:
    """Streaming voice activity detector.

    Feed it 512-sample float32 chunks at 16 kHz. Returns a speech
    probability in [0, 1]. State persists across calls; call reset()
    between independent streams.
    """

    def __init__(
        self,
        model_path: str | None = None,
        sample_rate: int = 16000,
        num_threads: int = 1,
    ) -> None:
        if sample_rate != 16000:
            raise ValueError("Only 16 kHz is supported by this wrapper")

        path = model_path or _resolve_model_path()
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = num_threads
        opts.intra_op_num_threads = num_threads
        opts.log_severity_level = 3  # suppress warnings

        self.session = ort.InferenceSession(
            path,
            sess_options=opts,
            providers=["CPUExecutionProvider"],
        )
        self.sample_rate = sample_rate
        self._input_names = {i.name for i in self.session.get_inputs()}

        self._state = np.zeros(_STATE_SHAPE, dtype=np.float32)
        self._context = np.zeros((1, _CONTEXT_SAMPLES), dtype=np.float32)

        logger.info("Silero VAD (ONNX) loaded from %s", path)

    # ------------------------------------------------------------------
    def reset(self) -> None:
        self._state = np.zeros(_STATE_SHAPE, dtype=np.float32)
        self._context = np.zeros((1, _CONTEXT_SAMPLES), dtype=np.float32)

    # ------------------------------------------------------------------
    def __call__(self, chunk: np.ndarray) -> float:
        """Probability in [0, 1] that `chunk` contains speech."""
        if chunk.dtype != np.float32:
            chunk = chunk.astype(np.float32)
        if chunk.ndim == 2:
            chunk = chunk.flatten()
        if chunk.shape[0] != _CHUNK_SAMPLES:
            # Pad or trim so the shape always matches what the model expects.
            if chunk.shape[0] < _CHUNK_SAMPLES:
                pad = np.zeros(_CHUNK_SAMPLES, dtype=np.float32)
                pad[: chunk.shape[0]] = chunk
                chunk = pad
            else:
                chunk = chunk[:_CHUNK_SAMPLES]

        # Prepend the context window from the previous chunk.
        x = np.concatenate(
            [self._context, chunk.reshape(1, -1)], axis=1
        ).astype(np.float32)

        inputs = {
            "input": x,
            "state": self._state,
        }
        if "sr" in self._input_names:
            inputs["sr"] = np.array(self.sample_rate, dtype=np.int64)

        outputs = self.session.run(None, inputs)
        prob = float(outputs[0].item() if hasattr(outputs[0], "item")
                     else outputs[0])

        self._state = outputs[1].astype(np.float32)
        # Keep the last 64 samples as context for the next chunk.
        self._context = x[:, -_CONTEXT_SAMPLES:]

        return prob