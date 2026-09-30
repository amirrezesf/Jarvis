import numpy as np, sounddevice as sd
import config
from audio.base import AudioSource
from core.events import Utterance

class MicSource(AudioSource):
    def listen(self):
        input("\nPress Enter to start recording...")
        chunks = []
        with sd.InputStream(samplerate=config.SAMPLE_RATE, channels=1,
                            dtype="float32",
                            callback=lambda d, *_: chunks.append(d.copy())):
            input("Recording... press Enter to stop.")
        if not chunks:
            return None
        audio = np.concatenate(chunks).flatten()
        if len(audio) < config.SAMPLE_RATE * 0.3:
            return None
        return Utterance(audio, "mic")