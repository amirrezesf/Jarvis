"""
System-audio capture via parec subprocess + silero VAD.

Linux-specific: uses parec (PulseAudio/PipeWire) to capture from a
monitor source. sounddevice/PortAudio does not enumerate monitor
sources reliably on Fedora/PipeWire, so we shell out to parec.

parec outputs raw float32 little-endian PCM to stdout. We read fixed
blocks, feed them to silero VAD, and return one Utterance per detected
speech segment.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Any

import numpy as np
import torch

from jarvis import config
from jarvis.audio.base import AudioSource
from jarvis.core.events import Utterance

logger = logging.getLogger(__name__)


class LoopbackSource(AudioSource):
    def __init__(self, device: str | None = None) -> None:
        """device: PipeWire monitor source name. Falls back to config."""
        self.device = device if device is not None else config.LOOPBACK_DEVICE
        self.sample_rate = config.SAMPLE_RATE
        self._proc: subprocess.Popen | None = None

        if not self.device:
            from jarvis.audio.monitor import default_monitor_source
            detected = default_monitor_source()
            if detected:
                self.device = detected
                logger.info("Auto-detected monitor source: %s", detected)
            else:
                raise RuntimeError(
                    "No monitor source configured and none could be detected. "
                    "Set LOOPBACK_DEVICE in ~/.jarvis/config.json. "
                    "Run `pactl list short sources | grep monitor` to list them."
                )

        try:
            from silero_vad import load_silero_vad
        except ImportError as exc:
            raise RuntimeError(
                "silero-vad is not installed. Run: pip install silero-vad"
            ) from exc

        self._vad_model: Any = load_silero_vad()
        logger.info("silero VAD loaded (device=%s)", self.device)

    # ------------------------------------------------------------------
    def _ensure_proc(self) -> None:
        """Start parec if it isn't already running."""
        if self._proc is not None and self._proc.poll() is None:
            return

        cmd = [
            "parec",
            f"--device={self.device}",
            "--format=float32le",
            f"--rate={self.sample_rate}",
            "--channels=1",
            "--latency-msec=20",
            "--raw",
        ]
        logger.info("Starting parec: %s", " ".join(cmd))
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    # ------------------------------------------------------------------
    def _stop_proc(self) -> None:
        if self._proc is None:
            return
        try:
            self._proc.terminate()
            self._proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        finally:
            self._proc = None

    # ------------------------------------------------------------------
    def listen(self) -> Utterance | None:
        """Block until one VAD-detected speech segment completes.

        Returns None if the segment is too short to be useful.
        """
        self._ensure_proc()
        if self._proc is None or self._proc.stdout is None:
            return None

        block_size = int(self.sample_rate * config.VAD_BLOCK_MS / 1000)
        bytes_per_block = block_size * 4  # float32

        min_silence_blocks = int(
            config.VAD_MIN_SILENCE_MS / config.VAD_BLOCK_MS
        )
        max_segment_blocks = int(
            config.VAD_MAX_SEGMENT_S * 1000 / config.VAD_BLOCK_MS
        )

        chunks: list[np.ndarray] = []
        silence_count = 0
        recording = False

        try:
            while True:
                raw = self._proc.stdout.read(bytes_per_block)
                if not raw or len(raw) < bytes_per_block:
                    # parec died or stream ended.
                    logger.warning("parec stream ended (got %d bytes)", len(raw))
                    self._stop_proc()
                    return None

                chunk = np.frombuffer(raw, dtype=np.float32)
                prob = self._speech_probability(chunk)
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
                    chunks.append(chunk)
                    if silence_count >= min_silence_blocks:
                        audio = np.concatenate(chunks)
                        recording = False
                        result = self._finish_segment(audio)
                        if result is not None:
                            return result
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
            self._stop_proc()
            raise

    # ------------------------------------------------------------------
    def _finish_segment(self, audio: np.ndarray) -> Utterance | None:
        seconds = len(audio) / self.sample_rate
        if seconds < config.VAD_MIN_SPEECH_S:
            logger.debug("Dropped short segment (%.2fs)", seconds)
            return None
        logger.debug("Segment complete: %.2fs", seconds)
        return Utterance(audio, "system")

    # ------------------------------------------------------------------
    def close(self) -> None:
        self._stop_proc()

    # ------------------------------------------------------------------
    def _speech_probability(self, chunk: np.ndarray) -> float:
        """Run silero VAD on one frame and return the speech probability.

        Handles two API shapes across silero-vad versions:
          - model(chunk, sr)               -> tensor scalar
          - model(chunk, sr, return_seconds=False) -> tensor scalar
        """
        tensor = torch.from_numpy(chunk.copy())
        try:
            out = self._vad_model(tensor, self.sample_rate)
        except TypeError:
            # Some builds want an explicit keyword or a different signature.
            out = self._vad_model(tensor, self.sample_rate, return_seconds=False)

        # Handle outputs that are tensors, floats, or dicts.
        if isinstance(out, dict):
            out = out.get("speech_prob", out.get("prob", 0.0))
        if hasattr(out, "item"):
            return float(out.item())
        return float(out)