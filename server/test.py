"""
Quick test for the 9Router gateway.

Run from the project root:
    python test_9router.py
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# 9Router's OpenAI-compatible endpoint. The NPM package serves the API on
# port 20128 by default; the dashboard itself is on the same port.
BASE_URL = os.getenv("NINEROUTER_URL", "http://127.0.0.1:20128/v1")

# Your API key from the 9Router dashboard (Settings -> API Keys).
# Leave empty if auth is disabled in your local setup.
API_KEY = os.getenv("NINEROUTER_KEY", "sk-16169c59be78df59-j6oo6q-208b8c24")

# Either a Combo name you created (e.g. "jarvis-combo") or a specific
# model ID like "kr/claude-sonnet-4.5".
MODEL = os.getenv("NINEROUTER_MODEL", "opencode")

# Ask something in Persian, same as the Hermes test.
PROMPT = "سلام چطوری؟"

# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------
headers = {"Content-Type": "application/json"}
if API_KEY:
    headers["Authorization"] = f"Bearer {API_KEY}"

print(f"POST {BASE_URL}/chat/completions")
print(f"Model: {MODEL}")
print(f"Prompt: {PROMPT}")
print("-" * 60)

resp = requests.post(
    f"{BASE_URL}/chat/completions",
    headers=headers,
    json={
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT}],
        "stream": False,
    },
    timeout=120,
)

if resp.status_code != 200:
    print(f"HTTP {resp.status_code}")
    print(resp.text)
    resp.raise_for_status()

answer = resp.json()["choices"][0]["message"]["content"]
print("Answer:")
print(answer)