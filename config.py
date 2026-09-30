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