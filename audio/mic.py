import numpy as np
import sounddevice as sd

import config
from audio.base import AudioSource
from core.events import Utterance


class MicSource(AudioSource):
    def __init__(self, start_wait=None, stop_wait=None):
        """
        start_wait / stop_wait:
            Optional callables that block until the user wants to start
            or stop recording. If None, the terminal input() prompt is
            used (original behaviour).
        """
        self.start_wait = start_wait
        self.stop_wait = stop_wait

    def listen(self):
        if self.start_wait is None:
            input("\nPress Enter to start recording...")
        else:
            self.start_wait()

        chunks = []
        with sd.InputStream(
            samplerate=config.SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=lambda d, *_: chunks.append(d.copy()),
        ):
            if self.stop_wait is None:
                input("Recording... press Enter to stop.")
            else:
                self.stop_wait()

        if not chunks:
            return None
        audio = np.concatenate(chunks).flatten()
        if len(audio) < config.SAMPLE_RATE * 0.3:
            return None
        return Utterance(audio, "mic")