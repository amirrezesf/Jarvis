import os
import subprocess
import sys
import tempfile
import time


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
    from core.events import Utterance
    from core.logger import setup_logging
    from core.recorder import SessionRecorder
    from core.transcriber import Transcriber

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
    from core.logger import setup_logging
    from core.recorder import SessionRecorder
    from core.transcriber import Transcriber
    from audio.loopback import LoopbackSource

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


def _run_ui() -> None:
    from core.logger import setup_logging
    setup_logging()
    from ui.canvas import run_ui
    run_ui()


def _run_text_mode() -> None:
    from core.agent import Agent, AgentError
    from core.logger import setup_logging

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
    from audio.mic import MicSource
    from core.agent import Agent, AgentError
    from core.logger import setup_logging
    from core.recorder import SessionRecorder
    from core.transcriber import Transcriber

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
    else:
        _run_ui()


if __name__ == "__main__":
    main()