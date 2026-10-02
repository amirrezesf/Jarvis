import os
import subprocess
import sys
import tempfile
import time

from jarvis import config


def _load_audio_any(path: str):
    """Load any audio format to 16 kHz mono float32. Uses ffmpeg as fallback."""
    import numpy as np

    try:
        import soundfile as sf
        audio, sr = sf.read(path, dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if sr != 16000:
            new_len = int(len(audio) / sr * 16000)
            audio = np.interp(
                np.linspace(0, 1, new_len),
                np.linspace(0, 1, len(audio)),
                audio,
            ).astype(np.float32)
        return audio
    except Exception:
        pass

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", path, "-ar", "16000", "-ac", "1",
             "-f", "wav", tmp_path],
            check=True, capture_output=True,
        )
        import soundfile as sf
        audio, _ = sf.read(tmp_path, dtype="float32")
        return audio
    finally:
        os.unlink(tmp_path)


def _run_file_mode(path: str) -> None:
    from jarvis.core.events import Utterance
    from jarvis.core.logger import setup_logging
    from jarvis.core.recorder import SessionRecorder
    from jarvis.core.transcriber import Transcriber

    setup_logging()
    audio = _load_audio_any(path)
    seconds = len(audio) / 16000

    print(f"File: {path}")
    print(f"Duration: {seconds:.1f}s")
    print("Transcribing (this may take a while)...")

    stt = Transcriber()
    utt = Utterance(audio, "system")
    tr = stt.run(utt)

    print(f"Transcribe time: {tr.seconds:.2f}s")
    print("-" * 60)
    print(tr.text)
    print("-" * 60)

    rec = SessionRecorder()
    rec.start_session(mode="file_test")
    rec.log_turn(
        utt=utt,
        transcript=tr,
        reply=None,
        agent_seconds=None,
        extra={"file": path},
    )


def _run_listen_mode() -> None:
    from jarvis.core.logger import setup_logging
    from jarvis.core.recorder import SessionRecorder
    from jarvis.core.transcriber import Transcriber
    from jarvis.audio.loopback import LoopbackSource

    setup_logging()

    source = LoopbackSource()
    stt = Transcriber()
    recorder = SessionRecorder()
    session_id = recorder.start_session(mode="listen")

    print(f"Listener session: {session_id}")
    print("Capturing system audio. Ctrl+C to stop.")
    print("-" * 60)

    try:
        while True:
            utt = source.listen()
            if utt is None:
                continue
            try:
                tr = stt.run(utt)
            except Exception as exc:
                print(f"[transcribe error] {type(exc).__name__}: {exc}")
                continue

            print(f"[{tr.seconds:.2f}s] {tr.text}")
            recorder.log_turn(
                utt=utt,
                transcript=tr,
                reply=None,
                agent_seconds=None,
            )
    except KeyboardInterrupt:
        print("\nSession ended.")



def _run_text_mode() -> None:
    from jarvis.core.agent import Agent, AgentError
    from jarvis.core.logger import setup_logging

    setup_logging()
    agent = Agent()
    print("Text mode. Ctrl+C to quit.")
    try:
        while True:
            try:
                text = input("You: ")
            except EOFError:
                break
            if not text.strip():
                continue
            t0 = time.time()
            first = None
            print("Jarvis: ", end="", flush=True)
            try:
                for chunk in agent.ask_stream(text):
                    if first is None:
                        first = time.time() - t0
                    print(chunk, end="", flush=True)
                print(f"\n  [first token {first:.2f}s]" if first else "")
            except AgentError as exc:
                print(f"\n[agent error] {exc}")
    except KeyboardInterrupt:
        print("\nBye.")


def _run_terminal_voice() -> None:
    from jarvis.audio.mic import MicSource
    from jarvis.core.agent import Agent, AgentError
    from jarvis.core.logger import setup_logging
    from jarvis.core.recorder import SessionRecorder
    from jarvis.core.transcriber import Transcriber

    setup_logging()
    agent = Agent()
    recorder = SessionRecorder()
    recorder.start_session(mode="assistant_cli")
    source = MicSource()
    stt = Transcriber()

    print("Press Enter to start, Enter again to stop. Ctrl+C to quit.")
    try:
        while True:
            utt = source.listen()
            if utt is None:
                continue
            transcript = None
            reply_parts = []
            first_token = None
            error = None
            try:
                transcript = stt.run(utt)
                print(f"You ({transcript.seconds:.2f}s): {transcript.text}")
                t0 = time.time()
                print("Jarvis: ", end="", flush=True)
                for chunk in agent.ask_stream(transcript.text):
                    if first_token is None:
                        first_token = time.time() - t0
                    reply_parts.append(chunk)
                    print(chunk, end="", flush=True)
                print()
            except AgentError as exc:
                error = f"AgentError: {exc}"
                print(f"\n[agent error] {exc}")
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                print(f"\n[error] {exc}")

            recorder.log_turn(
                utt=utt,
                transcript=transcript,
                reply="".join(reply_parts) or None,
                agent_seconds=None,
                agent_first_token_seconds=first_token,
                error=error,
            )
    except KeyboardInterrupt:
        print("\nBye.")

def _split_segments(text: str) -> list[str]:
    """Split a transcript file into sentence-level segments for testing."""
    import re

    parts: list[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Persian and Latin sentence terminators.
        for piece in re.split(r"[.؟!?]+", line):
            piece = piece.strip()
            if piece:
                parts.append(piece)
    return parts


def _run_trigger_test(path: str) -> None:
    from jarvis.core.logger import setup_logging
    from jarvis.core.triggers import NameDetector

    setup_logging()

    with open(path, encoding="utf-8") as fh:
        text = fh.read()

    segments = _split_segments(text)
    detector = NameDetector()

    print(f"File:      {path}")
    print(f"Segments:  {len(segments)}")
    print(
        f"Threshold: fired >= {detector.threshold}, "
        f"candidates >= {detector.candidate_threshold}"
    )
    print(f"Variants:  {len(detector.variants)}")
    print("-" * 72)

    fired_count = 0
    candidate_count = 0

    for i, segment in enumerate(segments, 1):
        debug = "--all" in sys.argv
        events = detector.scan(segment, return_all=debug)
        for ev in events:
            candidate_count += 1
            tag = "FIRED" if ev.fired else "cand "
            if ev.fired:
                fired_count += 1
            print(f"[{i:>4}] {tag}  score={ev.score:5.1f}  variant={ev.matched_variant!r}")
            print(f"        evidence: {ev.evidence!r}")
            print(f"        context:  {ev.context[:110]}")

    print("-" * 72)
    print(f"Fired:                {fired_count}")
    print(f"Candidates (total):   {candidate_count}")
    
def _run_extract_test(path: str) -> None:
    from jarvis.core.extraction import Extractor, ExtractionError
    from jarvis.core.logger import setup_logging

    setup_logging()

    with open(path, encoding="utf-8") as fh:
        text = fh.read()

    segments = _split_segments(text)
    extractor = Extractor()

    print(f"File:      {path}")
    print(f"Segments:  {len(segments)}")
    print(f"Model:     {extractor.model}")
    print(f"Window:    {config.EXTRACTION_WINDOW_SEGMENTS}")
    print("-" * 72)

    total = 0
    for i in range(1, len(segments) + 1):
        window = segments[:i]
        try:
            records = extractor.extract(window)
        except ExtractionError as exc:
            print(f"[{i:>4}] ERROR: {exc}")
            continue

        for rec in records:
            total += 1
            print(
                f"[{i:>4}] {rec.trigger_type:>11}  action={rec.action:<11} "
                f"args={rec.args}  scope={rec.scope}  conf={rec.confidence:.2f}"
            )
            print(f"        src:  {rec.source_text[:110]}")
            if rec.reasoning:
                print(f"        why:  {rec.reasoning}")

    print("-" * 72)
    print(f"Total extracted: {total}")

def _run_decide_test(path: str) -> None:
    from jarvis.core.alarm import play as play_alarm
    from jarvis.core.logger import setup_logging
    from jarvis.core.pipeline import ListenerPipeline

    setup_logging()

    with open(path, encoding="utf-8") as fh:
        text = fh.read()

    segments = _split_segments(text)
    pipeline = ListenerPipeline()

    print(f"File:      {path}")
    print(f"Segments:  {len(segments)}")
    print(f"TTL:       {config.INSTRUCTION_TTL_SECONDS}s")
    print("-" * 72)

    total = 0
    for i, seg in enumerate(segments, 1):
        decisions = pipeline.feed(seg)

        if decisions:
            play_alarm()

        for d in decisions:
            total += 1
            print(f"[{i:>4}] DECISION  action={d.action}  args={d.args}")
            trig = (
                f"{d.trigger_evidence!r} (score={d.trigger_score:.0f})"
                if d.trigger_evidence else "(immediate)"
            )
            print(f"        trigger:     {trig}")
            print(f"        instruction: {d.instruction_source[:100]}")
            print(
                f"        scope={d.instruction_scope}  "
                f"conf={d.instruction_confidence:.2f}"
            )
            print(f"        why:         {d.reasoning}")

        pending = pipeline.state.pending()
        if pending:
            print(f"[{i:>4}] pending: {len(pending)}")

    print("-" * 72)
    print(f"Total decisions: {total}")

def _run_ui(mode: str = "assistant") -> None:
    from jarvis.core.logger import setup_logging
    setup_logging()
    from jarvis.ui.canvas import run_ui
    run_ui(mode=mode)



def _run_listener_ui() -> None:
    from jarvis.core.logger import setup_logging
    setup_logging()
    from jarvis.ui.canvas import run_listener_ui
    run_listener_ui()

def _run_execute_test(path: str) -> None:
    from jarvis.core.actions import Executor, Outcome
    from jarvis.core.logger import setup_logging
    from jarvis.core.pipeline import ListenerPipeline
    from jarvis.core.events import Decision

    setup_logging()

    with open(path, encoding="utf-8") as fh:
        text = fh.read()

    segments = _split_segments(text)
    pipeline = ListenerPipeline()
    executor = Executor()

    print(f"File:      {path}")
    print(f"Segments:  {len(segments)}")
    print(f"Dry-run:   {config.ACTION_DRY_RUN}")
    print(f"Confirm:   {config.ACTION_REQUIRE_CONFIRM}")
    print("-" * 72)

    for i, seg in enumerate(segments, 1):
        decisions = pipeline.feed(seg)
        for d in decisions:
            outcome = executor.submit(d)
            tag = outcome.value.upper()
            print(f"[{i:>4}] {tag:<9} action={d.action}  args={d.args}")

    pending = executor.pending()
    if pending:
        print()
        print(f"Pending confirmations: {len(pending)}")
        for p in pending:
            print(f"  id={p.id}  action={p.decision.action}  "
                  f"args={p.decision.args}")
        print()
        print("Simulating approval of all pending actions...")
        for p in list(pending):
            outcome = executor.approve(p.id)
            print(f"  id={p.id} -> {outcome.value.upper()}")

        from jarvis.core.actions import DryRunBackend
        backend = executor.backend
        if isinstance(backend, DryRunBackend):
            print()
            print("Backend recorded:")
            for action, args in backend.executed:
                print(f"  {action}  {args}")

    print("-" * 72)

def main() -> None:
    args = sys.argv[1:]
    if "--text" in args:
        _run_text_mode()
    elif "--cli" in args:
        _run_terminal_voice()
    elif "--listen" in args:
        _run_listen_mode()
    elif "--file" in args:
        idx = args.index("--file")
        if idx + 1 >= len(args):
            print("Usage: python main.py --file <path>")
            sys.exit(1)
        _run_file_mode(args[idx + 1])
    elif "--trigger-test" in args:
        idx = args.index("--trigger-test")
        if idx + 1 >= len(args):
            print("Usage: python main.py --trigger-test <transcript.txt>")
            sys.exit(1)
        _run_trigger_test(args[idx + 1])
    elif "--extract-test" in args:
        idx = args.index("--extract-test")
        if idx + 1 >= len(args):
            print("Usage: python main.py --extract-test <transcript.txt>")
            sys.exit(1)
        _run_extract_test(args[idx + 1])
    elif "--decide-test" in args:
        idx = args.index("--decide-test")
        if idx + 1 >= len(args):
            print("Usage: python main.py --decide-test <transcript.txt>")
            sys.exit(1)
        _run_decide_test(args[idx + 1])
    elif "--listen-ui" in args:
        _run_listener_ui()
    elif "--execute-test" in args:
        idx = args.index("--execute-test")
        if idx + 1 >= len(args):
            print("Usage: python main.py --execute-test <transcript.txt>")
            sys.exit(1)
        _run_execute_test(args[idx + 1])
    else:
        _run_ui()


if __name__ == "__main__":
    main()