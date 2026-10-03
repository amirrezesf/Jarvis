"""
System-audio capture with VAD segmentation.

Two backends:
  Linux:   parec subprocess reading raw float32 PCM from a PipeWire
           monitor source. sounddevice/PortAudio doesn't enumerate
           monitor sources reliably on Fedora/PipeWire.
  Windows: the soundcard library, which wraps WASAPI loopback mode.

Both produce the same output: one Utterance per VAD-detected speech
segment, tagged source="system".
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time

import numpy as np

from jarvis import config
from jarvis.audio.base import AudioSource
from jarvis.audio.vad import SileroVAD
from jarvis.core.events import Utterance

logger = logging.getLogger(__name__)


class LoopbackSource(AudioSource):
    def __init__(self, device: str | None = None) -> None:
        self.device = device if device is not None else config.LOOPBACK_DEVICE
        self.sample_rate = config.SAMPLE_RATE
        self._proc: subprocess.Popen | None = None
        self._recorder = None

        if not self.device:
            from jarvis.audio.monitor import default_monitor_source
            detected = default_monitor_source()
            if detected:
                self.device = detected
                logger.info("Auto-detected capture source: %s", detected)
            else:
                raise RuntimeError(
                    "No capture source configured and none could be detected. "
                    "Set LOOPBACK_DEVICE in ~/.jarvis/config.json."
                )

        self._vad_model = SileroVAD(sample_rate=self.sample_rate)
        self._platform = "win32" if sys.platform == "win32" else "posix"
        logger.info(
            "Loopback source ready (platform=%s device=%s)",
            self._platform, self.device,
        )

    # ==================================================================
    # Public API
    # ==================================================================
    def listen(self) -> Utterance | None:
        """Block until one VAD-detected speech segment completes."""
        if self._platform == "win32":
            return self._listen_soundcard()
        return self._listen_parec()

    def close(self) -> None:
        """Release the underlying capture resources."""
        self._stop_proc()
        self._close_recorder()

    # ==================================================================
    # Linux: parec subprocess
    # ==================================================================
    def _ensure_proc(self) -> None:
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

    def _listen_parec(self) -> Utterance | None:
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
                    logger.warning("parec stream ended")
                    self._stop_proc()
                    return None
                chunk = np.frombuffer(raw, dtype=np.float32)

                prob = self._vad_model(chunk)
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

    # ==================================================================
    # Windows: soundcard WASAPI loopback
    # ==================================================================
    def _ensure_recorder(self) -> None:
        if self._recorder is not None:
            return

        import soundcard as sc

        speaker = None
        if self.device:
            try:
                speaker = sc.get_speaker(self.device)
            except Exception:
                speaker = None
        if speaker is None:
            speaker = sc.default_speaker()

        loopback = sc.get_microphone(
            id=str(speaker.name), include_loopback=True,
        )
        self._recorder = loopback.recorder(samplerate=self.sample_rate)
        self._recorder.__enter__()
        logger.info("soundcard recorder opened on %s", speaker.name)

    def _close_recorder(self) -> None:
        if self._recorder is None:
            return
        try:
            self._recorder.__exit__(None, None, None)
        except Exception:
            pass
        finally:
            self._recorder = None

    def _listen_soundcard(self) -> Utterance | None:
        self._ensure_recorder()
        if self._recorder is None:
            return None

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

        try:
            while True:
                try:
                    data = self._recorder.record(numframes=block_size)
                except Exception as exc:
                    logger.error("soundcard record failed: %s", exc)
                    self._close_recorder()
                    return None

                if data is None or len(data) == 0:
                    # WASAPI loopback can return nothing while the
                    # speaker is silent. Sleep briefly and retry rather
                    # than treating it as silence and burning a VAD tick.
                    time.sleep(config.VAD_BLOCK_MS / 1000)
                    continue

                # data shape is (frames, channels); average to mono.
                if data.ndim == 2 and data.shape[1] > 1:
                    chunk = data.mean(axis=1).astype(np.float32)
                else:
                    chunk = np.asarray(data, dtype=np.float32).flatten()

                prob = self._vad_model(chunk)
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
            self._close_recorder()
            raise

    # ==================================================================
    # Shared
    # ==================================================================
    def _finish_segment(self, audio: np.ndarray) -> Utterance | None:
        seconds = len(audio) / self.sample_rate
        if seconds < config.VAD_MIN_SPEECH_S:
            logger.debug("Dropped short segment (%.2fs)", seconds)
            return None
        logger.debug("Segment complete: %.2fs", seconds)
        return Utterance(audio, "system")