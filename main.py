import sys
import time

from audio.mic import MicSource
from core.agent import Agent, AgentError
from core.logger import setup_logging
from core.recorder import SessionRecorder
from core.transcriber import Transcriber


def _stream_and_log(agent, text, recorder, utt, transcript):
    """Call the agent with streaming, print tokens live, log the turn.

    Returns the full reply string (or None if nothing arrived).
    """
    t0 = time.time()
    first_token_seconds = None
    parts: list[str] = []
    error = None

    print("Jarvis: ", end="", flush=True)
    try:
        for chunk in agent.ask_stream(text):
            if first_token_seconds is None:
                first_token_seconds = time.time() - t0
            parts.append(chunk)
            print(chunk, end="", flush=True)
        print()
    except AgentError as exc:
        error = f"AgentError: {exc}"
        print(f"\n[agent error] {exc}")
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        print(f"\n[error] {exc}")

    agent_seconds = time.time() - t0
    reply = "".join(parts) or None

    if utt is not None and recorder is not None:
        recorder.log_turn(
            utt=utt,
            transcript=transcript,
            reply=reply,
            agent_seconds=agent_seconds,
            agent_first_token_seconds=first_token_seconds,
            error=error,
        )

    return reply


def main():
    setup_logging()

    agent = Agent()
    recorder = SessionRecorder()

    # ------------------------------------------------------------------
    # Text-only mode: skip the mic, type directly into the agent.
    # ------------------------------------------------------------------
    if "--text" in sys.argv:
        print("Text mode. Ctrl+C to quit.")
        try:
            while True:
                try:
                    text = input("You: ")
                except EOFError:
                    break
                _stream_and_log(agent, text, None, None, None)
        except KeyboardInterrupt:
            print("\nBye.")
        return

    # ------------------------------------------------------------------
    # Voice mode.
    # ------------------------------------------------------------------
    source = MicSource()
    stt = Transcriber()

    print("Press Enter to start, Enter again to stop. Ctrl+C to quit.")

    try:
        while True:
            utt = source.listen()
            if utt is None:
                continue

            transcript = None
            try:
                transcript = stt.run(utt)
                print(f"You ({transcript.seconds:.2f}s): {transcript.text}")
            except Exception as exc:
                print(f"[transcribe error] {type(exc).__name__}: {exc}")
                recorder.log_turn(
                    utt=utt,
                    transcript=None,
                    reply=None,
                    agent_seconds=None,
                    error=f"TranscribeError: {exc}",
                )
                continue

            _stream_and_log(agent, transcript.text, recorder, utt, transcript)

    except KeyboardInterrupt:
        print("\nBye.")


if __name__ == "__main__":
    main()

    