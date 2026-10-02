WHISPER_MODEL: str = "large-v3-turbo"
WHISPER_MODEL: str = "large-v3-turbo"
DEVICE: str = "cuda"
COMPUTE_TYPE: str = "float16"
LANGUAGE: str = "fa"
LOOPBACK_DEVICE: str = ""
SAMPLE_RATE = 16000
PTT_KEY = "right ctrl"
SAVE_RECORDINGS = True

# ---------------------------------------------------------------------------
# 9Router Configuration
# ---------------------------------------------------------------------------
# 9Router's OpenAI-compatible endpoint
NINEROUTER_URL = "http://localhost:20128/v1"

# API key from the 9Router dashboard (empty string if auth is disabled)
NINEROUTER_KEY = "sk-16169c59be78df59-j6oo6q-208b8c24"

# The name of the Combo you created in the 9Router dashboard
NINEROUTER_COMBO_NAME = "opencode"

# Timeout in seconds (9Router fallback chains can take a while)
NINEROUTER_TIMEOUT = 120.0
# Retry policy for transient upstream failures (503s, overloaded providers).
# A retry only happens if the failure occurred before any token was shown.
NINEROUTER_MAX_RETRIES = 2       # 3 total attempts
NINEROUTER_RETRY_DELAY = 1.0     # seconds between attempts

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = "INFO"               # "DEBUG" to see agent request logs
LOG_DIR = "logs"
SESSIONS_DIR = "logs/sessions"

# ---------------------------------------------------------------------------
# Whisper decoding options
# ---------------------------------------------------------------------------
# faster-whisper's defaults are tuned for long-form audio. For short,
# independent utterances (Enter-to-talk), condition_on_previous_text
# hurts: the model tries to continue the previous sentence instead of
# transcribing the current one.
BEAM_SIZE = 5
CONDITION_ON_PREVIOUS_TEXT = False
VAD_FILTER = True

# Seeded into Whisper to bias spelling and terminology. Keep it short
# (~200 tokens max); long prompts slow decoding and over-bias the model.
INITIAL_PROMPT = (
    "این یک جلسه درسی دانشگاهی به زبان فارسی است. "
    "واژه‌های مهم: امیررضا اسفندیاری، HIT، اسکای‌روم، SkyroomBot."
)

# Kept: hotwords demonstrably fixed کود→کد, اسکاراتومی→اسکاروتومی,
# فلپ→فلاپ, سائد→ساعد on live Skyroom audio with large-v3.
HOTWORDS = (
    "ضایعه, ناحیه, اسکاروتومی, اسکارکتومی, اکسپلور, عصب دیژیتال, "
    "پیوند پوستی, فلاپ, ساعد, ارتوپدی, کد تعدیلی, جراح"
)

# ---------------------------------------------------------------------------
# Listener mode: loopback capture + VAD
# ---------------------------------------------------------------------------
# PipeWire monitor source. Find yours with:
#   python -c "import sounddevice as sd; print(sd.query_devices())"
# On Fedora/PipeWire it looks like:
#   "alsa_output.pci-0000_00_1f.3.analog-stereo.monitor"
# You can pass either the device name string or its integer index.
# VAD (silero) parameters for segmenting continuous audio.
VAD_THRESHOLD = 0.5          # speech probability threshold (0..1)
VAD_MIN_SILENCE_MS = 700     # silence needed to close a segment
VAD_MIN_SPEECH_S = 0.6       # discard segments shorter than this
VAD_MAX_SEGMENT_S = 45.0     # force-close a segment at this length. 60 for large-v3
VAD_BLOCK_MS = 32            # VAD frame size (512 samples @ 16 kHz)


# ---------------------------------------------------------------------------
# Trigger detection: name matching
# ---------------------------------------------------------------------------
# Persian spelling variants of the user's name. The detector normalizes
# these once at startup (Arabic ي -> Persian ی, ZWNJ -> space, etc.).
NAME_VARIANTS = [
    "امیررضا اسفندیاری",
    "امیر رضا اسفندیاری",
    "اسفندیاری",
]

# 0-100. Higher = stricter = fewer false positives.
# 80 is a starting point; tune after testing on real recordings.
NAME_MATCH_THRESHOLD = 80

# Below this, candidates are ignored entirely (not even logged).
# Between this and NAME_MATCH_THRESHOLD, they are logged but not fired.
NAME_MATCH_CANDIDATE_THRESHOLD = 65

# Variants shorter than this many characters are skipped entirely,
# to avoid matches on short common words.
NAME_MATCH_MIN_LENGTH = 4
NAME_BUFFER_SEGMENTS = 3


# ---------------------------------------------------------------------------
# LLM layer: instruction extraction
# ---------------------------------------------------------------------------
# Model / combo name for extraction. Runs once per segment, so latency
# budget is generous — we prioritize reliability over raw speed.
EXTRACTION_MODEL = "opencode"

# Recent segments sent as context. The LATEST is always included.
EXTRACTION_WINDOW_SEGMENTS = 5

# Discard records below this confidence.
EXTRACTION_CONFIDENCE_MIN = 0.7

# One retry on malformed output or transient failure.
EXTRACTION_MAX_RETRIES = 1

# Timeout for one extraction call.
EXTRACTION_TIMEOUT = 90.0
# Structured extraction should be deterministic. Reasoning models may
# still vary, but temperature 0 removes the largest noise source.
EXTRACTION_TEMPERATURE = 1.0
# Soft cap on the Persian context summary attached to extracted
# instructions. The prompt asks for "about this many"; the code
# hard-truncates as a safety net.
EXTRACTION_CONTEXT_MAX_WORDS = 25


# ---------------------------------------------------------------------------
# Matching + decision
# ---------------------------------------------------------------------------
# How long an extracted instruction stays pending before it's considered
# stale. Roll calls finish in a couple of minutes; anything older than
# this is almost certainly from a previous activity.
INSTRUCTION_TTL_SECONDS = 5 * 60


# ---------------------------------------------------------------------------
# Alarm
# ---------------------------------------------------------------------------
# Play a short sound whenever a decision fires — immediate or trigger-matched.
# Both fire in real time during a live class, and both need your attention.
ALARM_ENABLED = True

# Path to a sound file. paplay handles .oga and .wav; aplay only .wav.
# Fedora ships a set of notification sounds under
#   /usr/share/sounds/freedesktop/stereo/
# Good candidates: bell.oga, complete.oga, message.oga, message-new-instant.oga
ALARM_SOUND_PATH = "default"



# ---------------------------------------------------------------------------
# LLM layer: extraction backend
# ---------------------------------------------------------------------------
# "cloud"  -> use 9Router at NINEROUTER_URL (existing behavior)
# "local"  -> use a local OpenAI-compatible server (Ollama, llama.cpp, vLLM)
EXTRACTION_BACKEND = "local"

# Local backend settings. Ollama exposes an OpenAI-compatible endpoint
# at /v1 by default, so no code changes are needed to switch — only
# these three values.
LOCAL_LLM_URL = "http://localhost:11434/v1"
LOCAL_LLM_KEY = ""  # Ollama ignores this; kept for compatibility
LOCAL_EXTRACTION_MODEL = "qwen2.5:3b"

# Cloud model (existing)
EXTRACTION_MODEL = "opencode"

# ---------------------------------------------------------------------------
# Action execution
# ---------------------------------------------------------------------------
# Master switch. If False, no action ever executes.
ACTION_EXECUTION_ENABLED = True

# Dry-run: type_number and send_chat log what they WOULD have done and
# stop there. notify_me is never dry-run — showing a notification is
# harmless by definition. Set to False when the SkyroomBackend is wired in.
ACTION_DRY_RUN = True

# Actions that require confirmation before executing. Everything else runs
# immediately. Irreversible actions should stay listed here during rollout.
ACTION_REQUIRE_CONFIRM = ["type_number", "send_chat"]

# Actions to skip entirely, without confirmation or execution. Useful for
# temporarily muting a specific action type.
ACTION_DISABLED: list[str] = []


from jarvis.core.config_loader import apply_overrides as _apply_overrides
_apply_overrides(globals())
del _apply_overrides