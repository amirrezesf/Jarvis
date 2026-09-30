"""Dump raw SSE lines from 9Router to see what's actually coming through."""

import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("NINEROUTER_URL", "http://127.0.0.1:20128/v1")
API_KEY = os.getenv("NINEROUTER_KEY", "")
MODEL = os.getenv("NINEROUTER_MODEL", "opencode")
PROMPT = sys.argv[1] if len(sys.argv) > 1 else "سلام چطوری؟"

headers = {"Content-Type": "application/json"}
if API_KEY:
    headers["Authorization"] = f"Bearer {API_KEY}"

print(f"POST {BASE_URL}/chat/completions  model={MODEL}")
print(f"Prompt: {PROMPT}")
print("-" * 70)

resp = requests.post(
    f"{BASE_URL}/chat/completions",
    headers=headers,
    json={
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT}],
        "stream": True,
    },
    timeout=120,
    stream=True,
)

print(f"HTTP {resp.status_code}")
print(f"Content-Type: {resp.headers.get('Content-Type')}")
print("-" * 70)

buffer = ""
line_count = 0
for raw in resp.iter_content(chunk_size=1024):
    if not raw:
        continue
    buffer += raw.decode("utf-8", errors="replace")
    while "\n" in buffer:
        line, buffer = buffer.split("\n", 1)
        line = line.rstrip("\r")
        if line:
            line_count += 1
            print(f"{line_count:03d}| {line[:300]}")

print("-" * 70)
print(f"Total lines: {line_count}")