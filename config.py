WHISPER_MODEL = "large-v3-turbo"
DEVICE = "cuda"
COMPUTE_TYPE = "float16" #int8_float16 for large-v3
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
LOOPBACK_DEVICE = "alsa_output.pci-0000_00_1f.3.analog-stereo.monitor"   # None = system default input (not what you want for class)

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