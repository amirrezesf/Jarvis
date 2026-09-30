WHISPER_MODEL = "large-v3-turbo"
DEVICE = "cuda"
COMPUTE_TYPE = "float16"
LANGUAGE = 'fa'          # "en" / "fa" to force
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

# Seeded into Whisper to bias spelling of names and jargon. Keep it short;
# long prompts slow decoding slightly and over-bias the model.
# Edit this to match how you actually say things.
INITIAL_PROMPT = (
    "این گفتگویی است با امیررضا اسفندیاری. "
    "واژه‌های مهم: HIT، اسکای‌روم، SkyroomBot، Jarvis، Whisper."
)