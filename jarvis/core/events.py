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
    seconds: float     
        # transcription time, for latency tracking

@dataclass
class InstructionRecord:
    """One extracted instruction from the transcript."""
    trigger_type: str        # "name_called" | "keyword" | "immediate" | "none"
    action: str              # "type_number" | "send_chat" | "notify_me" | "none"
    args: dict               # action-specific arguments
    scope: str               # "personal" | "broadcast"
    confidence: float        # 0.0 .. 1.0
    source_text: str         # the segment the instruction came from
    context_summary: str = ""   # short Persian summary of the preceding segments
    reasoning: str = ""

from datetime import datetime

@dataclass
class Decision:
    """The final action chosen by the pipeline for one trigger fire."""
    ts: datetime
    action: str
    args: dict
    trigger_evidence: str
    trigger_score: float
    instruction_source: str
    instruction_scope: str
    instruction_confidence: float
    reasoning: str
    context_summary: str = ""

@dataclass
class TriggerEvent:
    type: str               # e.g. "name_called"
    matched_variant: str    # the config variant that matched
    evidence: str           # the span in the transcript that matched
    score: float            # 0..100
    context: str            # the full buffered text at match time
    fired: bool             # True if score >= threshold, else candidate only

