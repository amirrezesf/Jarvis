"""
Edge-case tests for the listener decision pipeline.

Runs four scenarios against the real extractor and pipeline:
    1. Overlap   — pending rule + immediate instruction in one segment
    2. Expiry    — pending instruction ages out before the name is called
    3. Two       — two rules pending, one name called
    4. Unclear   — personal address with no specific action

Requires a running 9Router gateway and the same config as the app.
Makes real LLM calls: allow ~30–60 seconds total.

Run from the project root:
    python tools/test_edge_cases.py
"""

from __future__ import annotations

from pathlib import Path
import sys
import time
# Make the project root importable when running this file directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


from jarvis.core.events import Decision
from jarvis.core.logger import setup_logging
from jarvis.core.pipeline import ListenerPipeline
from jarvis.core.state import InstructionState


def _describe(decisions: list[Decision]) -> str:
    if not decisions:
        return "0 decisions"
    parts = []
    for d in decisions:
        if d.action == "type_number":
            parts.append(f"type_number n={d.args.get('n')}")
        elif d.action == "notify_me":
            txt = str(d.args.get("text", ""))[:40]
            parts.append(f"notify_me {txt!r}")
        elif d.action == "send_chat":
            txt = str(d.args.get("text", ""))[:40]
            parts.append(f"send_chat {txt!r}")
        else:
            parts.append(f"{d.action} {d.args}")
    return f"{len(decisions)}: " + "; ".join(parts)


def _run_scenario(
    name: str,
    steps: list[tuple],
    *,
    ttl_seconds: int | None = None,
    expect_decisions: int | None = None,
    expect_action: str | None = None,
    expect_n: int | None = None,
    expect_pending: int | None = None,
) -> bool:
    print()
    print("=" * 72)
    print(name)
    print("=" * 72)

    pipeline = ListenerPipeline()
    if ttl_seconds is not None:
        pipeline.state = InstructionState(ttl_seconds=ttl_seconds)

    all_decisions: list[Decision] = []

    for step in steps:
        kind = step[0]
        if kind == "feed":
            text = step[1]
            decisions = pipeline.feed(text)
            all_decisions.extend(decisions)
            pending = len(pipeline.state.pending())
            print(f"  feed: {text[:70]}")
            print(f"        -> {_describe(decisions)}  (pending={pending})")
        elif kind == "sleep":
            print(f"  sleep {step[1]}s")
            time.sleep(step[1])

    print()
    print(f"  Total: {_describe(all_decisions)}")

    failures: list[str] = []

    if expect_decisions is not None and len(all_decisions) != expect_decisions:
        failures.append(
            f"expected {expect_decisions} decisions, got {len(all_decisions)}"
        )

    if expect_action is not None:
        got = all_decisions[0].action if all_decisions else "(none)"
        if got != expect_action:
            failures.append(f"expected action={expect_action}, got {got}")

    if expect_n is not None:
        got = all_decisions[0].args.get("n") if all_decisions else None
        if got != expect_n:
            failures.append(f"expected n={expect_n}, got {got}")

    if expect_pending is not None:
        got = len(pipeline.state.pending())
        if got != expect_pending:
            failures.append(f"expected {expect_pending} pending, got {got}")

    if failures:
        for f in failures:
            print(f"  FAIL: {f}")
        return False

    print("  PASS")
    return True


def main() -> int:
    setup_logging()

    results: list[tuple[str, bool]] = []

    # ------------------------------------------------------------------
    # 1. Overlap
    # ------------------------------------------------------------------
    results.append((
        "1. Overlap (pending rule + immediate)",
        _run_scenario(
            "Scenario 1 — Overlap",
            [
                (
                    "feed",
                    "دانشجویان عزیز، بعد از اینکه اسمتون رو خوندم "
                    "عدد یک رو تایپ کنید.",
                ),
                (
                    "feed",
                    "امیررضا اسفندیاری، لطفاً عدد دو را وارد کن.",
                ),
            ],
            expect_decisions=1,
            expect_action="type_number",
            expect_n=2,
            expect_pending=1,
        ),
    ))

    # ------------------------------------------------------------------
    # 2. Expiry
    # ------------------------------------------------------------------
    results.append((
        "2. Expiry",
        _run_scenario(
            "Scenario 2 — Expiry",
            [
                (
                    "feed",
                    "دانشجویان، بعد از اینکه اسمتون رو خوندم "
                    "عدد یک رو تایپ کنید.",
                ),
                ("sleep", 3),
                ("feed", "امیررضا اسفندیاری؟"),
            ],
            ttl_seconds=2,
            expect_decisions=0,
            expect_pending=0,
        ),
    ))

    # ------------------------------------------------------------------
    # 3. Two pending, one name
    # ------------------------------------------------------------------
    results.append((
        "3. Two pending, one name",
        _run_scenario(
            "Scenario 3 — Two pending, one name",
            [
                (
                    "feed",
                    "دانشجویان، بعد از اینکه اسمتون رو خوندم "
                    "عدد یک رو تایپ کنید.",
                ),
                (
                    "feed",
                    "دانشجویان، بعد از اینکه اسمتون رو خوندم "
                    "عدد دو رو تایپ کنید.",
                ),
                ("feed", "امیررضا اسفندیاری؟"),
            ],
            expect_decisions=1,
            expect_action="type_number",
            expect_n=2,
            expect_pending=1,
        ),
    ))

    # ------------------------------------------------------------------
    # 4. Unclear action
    # ------------------------------------------------------------------
    results.append((
        "4. Unclear action",
        _run_scenario(
            "Scenario 4 — Unclear action",
            [
                ("feed", "امیررضا اسفندیاری، یه کاری بکن."),
            ],
            expect_decisions=1,
            expect_action="notify_me",
        ),
    ))

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print()
    print("=" * 72)
    print("Summary")
    print("=" * 72)
    passed = 0
    for name, ok in results:
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}")
        if ok:
            passed += 1

    print()
    print(f"  {passed}/{len(results)} scenarios passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())