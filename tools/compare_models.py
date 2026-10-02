"""
Compare extraction backends: latency and accuracy.

Runs the same test segments through both the local and cloud backends,
N times each, and scores the results against expected values.

Usage:
    python tools/compare_models.py tests/extract_mixed.txt --runs 3
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from core.extraction import Extractor, ExtractionError
from core.logger import setup_logging


# ---------------------------------------------------------------------------
# Expected results
# ---------------------------------------------------------------------------
# Segment index (1-based) -> expected record fields.
# "instruction" means a record is expected; absence means no record.
EXPECTED = {
    3: {"trigger_type": "name_called", "action": "type_number",
        "args": {"n": 1}, "scope": "broadcast"},
    4: {"trigger_type": "immediate", "action": "type_number",
        "args": {"n": 2}, "scope": "personal"},
}


def _split_segments(text: str) -> list[str]:
    parts = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        for piece in re.split(r"[.؟!?]+", line):
            piece = piece.strip()
            if piece:
                parts.append(piece)
    return parts


# ---------------------------------------------------------------------------
# Run one backend
# ---------------------------------------------------------------------------
def run_backend(
    name: str,
    base_url: str,
    api_key: str,
    model: str,
    segments: list[str],
    runs: int,
) -> list[tuple[int, float, list]]:
    """Returns list of (segment_index, extract_seconds, records)."""
    extractor = Extractor(base_url=base_url, api_key=api_key, model=model)
    results = []

    for run in range(runs):
        for i, _ in enumerate(segments, 1):
            window = segments[:i]
            t0 = time.perf_counter()
            try:
                records = extractor.extract(window)
            except ExtractionError:
                records = []
            elapsed = time.perf_counter() - t0
            results.append((i, elapsed, records))

    return results


# ---------------------------------------------------------------------------
# Score
# ---------------------------------------------------------------------------
def score(results: list[tuple[int, float, list]]) -> dict:
    times = []
    counters = {
        "action": [0, 0],
        "trigger_type": [0, 0],
        "scope": [0, 0],
        "args": [0, 0],
    }
    per_segment: dict[int, list] = {}

    for i, elapsed, records in results:
        times.append(elapsed)
        per_segment.setdefault(i, []).append((elapsed, records))

        expected = EXPECTED.get(i)
        if expected is None:
            continue

        if not records:
            for k in counters:
                counters[k][1] += 1
            continue

        rec = records[0]
        counters["action"][1] += 1
        counters["trigger_type"][1] += 1
        counters["scope"][1] += 1
        counters["args"][1] += 1

        if rec.action == expected["action"]:
            counters["action"][0] += 1
        if rec.trigger_type == expected["trigger_type"]:
            counters["trigger_type"][0] += 1
        if rec.scope == expected["scope"]:
            counters["scope"][0] += 1
        if rec.args == expected["args"]:
            counters["args"][0] += 1

    return {
        "mean": sum(times) / len(times) if times else 0.0,
        "min": min(times) if times else 0.0,
        "max": max(times) if times else 0.0,
        "counters": counters,
        "per_segment": per_segment,
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def pct(ok: int, total: int) -> str:
    if total == 0:
        return "  n/a"
    return f"{ok}/{total} ({100*ok//total}%)"


def print_report(name: str, s: dict) -> None:
    print(f"\n{name}")
    print(f"  Extraction time:   mean={s['mean']:.2f}s  "
          f"min={s['min']:.2f}s  max={s['max']:.2f}s")
    print(f"  action correct:    {pct(*s['counters']['action'])}")
    print(f"  trigger_type:      {pct(*s['counters']['trigger_type'])}")
    print(f"  scope:             {pct(*s['counters']['scope'])}")
    print(f"  args:              {pct(*s['counters']['args'])}")

    # Per-segment breakdown
    print(f"  Per-segment:")
    for i in sorted(s["per_segment"].keys()):
        runs = s["per_segment"][i]
        if i not in EXPECTED:
            continue
        times = [t for t, _ in runs]
        recs = [r for _, r in runs]
        # Count how many runs got the expected record
        exp = EXPECTED[i]
        hits = sum(
            1 for recs_ in recs
            if recs_ and recs_[0].action == exp["action"]
        )
        print(f"    seg {i}: {hits}/{len(runs)} runs with "
              f"expected action; time {min(times):.2f}-{max(times):.2f}s")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="test transcript file")
    parser.add_argument("--runs", type=int, default=3,
                        help="runs per segment (default 3)")
    args = parser.parse_args()

    setup_logging()

    text = Path(args.file).read_text(encoding="utf-8")
    segments = _split_segments(text)

    print("=" * 72)
    print(f"File:             {args.file}")
    print(f"Segments:         {len(segments)}")
    print(f"Runs per segment: {args.runs}")
    print(f"Local model:      {config.LOCAL_EXTRACTION_MODEL} "
          f"@ {config.LOCAL_LLM_URL}")
    print(f"Cloud model:      {config.EXTRACTION_MODEL} "
          f"@ {config.NINEROUTER_URL}")
    print("=" * 72)

    print("\nRunning LOCAL backend...")
    local_results = run_backend(
        "local",
        config.LOCAL_LLM_URL,
        config.LOCAL_LLM_KEY,
        config.LOCAL_EXTRACTION_MODEL,
        segments,
        args.runs,
    )

    print("Running CLOUD backend...")
    cloud_results = run_backend(
        "cloud",
        config.NINEROUTER_URL,
        config.NINEROUTER_KEY,
        config.EXTRACTION_MODEL,
        segments,
        args.runs,
    )

    print("\n" + "=" * 72)
    print("RESULTS")
    print("=" * 72)

    print_report(
        f"LOCAL — {config.LOCAL_EXTRACTION_MODEL}",
        score(local_results),
    )
    print_report(
        f"CLOUD — {config.EXTRACTION_MODEL}",
        score(cloud_results),
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())