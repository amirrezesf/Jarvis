"""
System-audio capture from a PipeWire monitor source, with silero VAD
segmentation. Emits Utterance(source="system") once per speech segment.

Linux-specific: relies on PipeWire/PulseAudio exposing a .monitor source
that sounddevice can open. On Fedora this is the default PipeWire setup.
"""

from __future__ import annotations

import logging

import numpy as np
import sounddevice as sd
import torch

import config
from audio.base import AudioSource
from core.events import Utterance

logger = logging.getLogger(__name__)


class LoopbackSource(AudioSource):
    def __init__(self, device=None) -> None:
        """device: monitor source name or integer index. Falls back to config."""
        self.device = device if device is not None else config.LOOPBACK_DEVICE
        self.sample_rate = config.SAMPLE_RATE

        try:
            from silero_vad import load_silero_vad
        except ImportError as exc:
            raise RuntimeError(
                "silero-vad is not installed. Run: pip install silero-vad"
            ) from exc

        # Load once; reused across listen() calls.
        self._vad_model = load_silero_vad()
        logger.info("silero VAD loaded (device=%s)", self.device or "default")

    # ------------------------------------------------------------------
    def listen(self) -> Utterance | None:
        """Block until one VAD-detected speech segment completes, then return it.

        Returns None if the segment is too short to be useful.
        """
        block_size = int(self.sample_rate * config.VAD_BLOCK_MS / 1000)
        min_silence_blocks = int(
            config.VAD_MIN_SILENCE_MS / config.VAD_BLOCK_MS
        )
        max_segment_blocks = int(
            config.VAD_MAX_SEGMENT_S * 1000 / config.VAD_BLOCK_MS
        )

        chunks: list[np.ndarray] = []
        silence_count = 0
        recording = False

        logger.debug(
            "Opening InputStream device=%s sr=%d block=%d",
            self.device or "default", self.sample_rate, block_size,
        )

        try:
            with sd.InputStream(
                device=self.device,
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=block_size,
            ) as stream:
                while True:
                    data, overflowed = stream.read(block_size)
                    if overflowed:
                        logger.warning("Audio input overflow")
                    chunk = data.flatten()

                    # silero expects (samples,) float32 tensor.
                    prob = float(
                        self._vad_model(
                            torch.from_numpy(chunk), self.sample_rate
                        ).item()
                    )
                    is_speech = prob > config.VAD_THRESHOLD

                    if is_speech:
                        if not recording:
                            recording = True
                            chunks = []
                            silence_count = 0
                        silence_count = 0
                        chunks.append(chunk)
                    elif recording:
                        silence_count += 1
                        chunks.append(chunk)  # include trailing silence

                        if silence_count >= min_silence_blocks:
                            audio = np.concatenate(chunks)
                            recording = False
                            result = self._finish_segment(audio)
                            if result is not None:
                                return result
                            # Too short: reset and keep listening.
                            chunks = []
                            silence_count = 0

                    if recording and len(chunks) >= max_segment_blocks:
                        audio = np.concatenate(chunks)
                        recording = False
                        result = self._finish_segment(audio)
                        if result is not None:
                            return result
                        chunks = []
                        silence_count = 0
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            logger.error("Loopback capture failed: %s", exc)
            raise

    # ------------------------------------------------------------------
    def _finish_segment(self, audio: np.ndarray) -> Utterance | None:
        seconds = len(audio) / self.sample_rate
        if seconds < config.VAD_MIN_SPEECH_S:
            logger.debug("Dropped short segment (%.2fs)", seconds)
            return None
        logger.debug("Segment complete: %.2fs", seconds)
        return Utterance(audio, "system")