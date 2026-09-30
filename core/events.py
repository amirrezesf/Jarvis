from dataclasses import dataclass
import numpy as np

@dataclass
class Utterance:
    audio: np.ndarray      # 16 kHz mono float32
    source: str            # "mic" or "system"

@dataclass
class Transcript:
    text: str
    source: str
    seconds: float         # transcription time, for latency tracking