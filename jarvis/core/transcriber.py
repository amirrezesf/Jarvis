import time
from jarvis.core import cuda
cuda.preload()

from faster_whisper import WhisperModel

from jarvis import config
from jarvis.core import corrections
from jarvis.core.events import Utterance, Transcript


class Transcriber:
    def __init__(self):
        self.model = WhisperModel(
            config.WHISPER_MODEL,
            device=config.DEVICE,
            compute_type=config.COMPUTE_TYPE,
        )

    def run(self, utt: Utterance) -> Transcript:
        t0 = time.time()
        segs, _ = self.model.transcribe(
            utt.audio,
            language=config.LANGUAGE,
            beam_size=config.BEAM_SIZE,
            condition_on_previous_text=config.CONDITION_ON_PREVIOUS_TEXT,
            vad_filter=config.VAD_FILTER,
            initial_prompt=config.INITIAL_PROMPT or None,
            hotwords=config.HOTWORDS or None,
        )
        text = " ".join(s.text.strip() for s in segs)
        text = corrections.apply(text)
        return Transcript(text, utt.source, time.time() - t0)