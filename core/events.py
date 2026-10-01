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

@dataclass
class InstructionRecord:
    """One extracted instruction from the transcript."""
    trigger_type: str        # "name_called" | "keyword" | "immediate" | "none"
    action: str              # "type_number" | "send_chat" | "notify_me" | "none"
    args: dict               # action-specific arguments
    scope: str               # "personal" | "broadcast"
    confidence: float        # 0.0 .. 1.0
    source_text: str         # the segment the instruction came from
    reasoning: str = ""      # short explanation from the extractor