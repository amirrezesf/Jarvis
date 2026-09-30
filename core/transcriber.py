import os
import time
import soundfile as sf
from faster_whisper import WhisperModel
import config
from core.events import Utterance, Transcript

class Transcriber:
    def __init__(self):
        self.model = WhisperModel(config.WHISPER_MODEL,
                                  device=config.DEVICE,
                                  compute_type=config.COMPUTE_TYPE)

    def run(self, utt: Utterance) -> Transcript:
        t0 = time.time()
        segs, _ = self.model.transcribe(utt.audio, language=config.LANGUAGE,
                                        vad_filter=True)
        text = " ".join(s.text.strip() for s in segs)
        return Transcript(text, utt.source, time.time() - t0)