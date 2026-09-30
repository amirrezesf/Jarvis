import sys
import time

from audio.mic import MicSource
from core.agent import Agent, AgentError
from core.logger import setup_logging
from core.recorder import SessionRecorder
from core.transcriber import Transcriber


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
                t0 = time.time()
                try:
                    reply = agent.ask(text)
                except AgentError as exc:
                    print(f"[agent error] {exc}")
                    continue
                print(f"Jarvis ({time.time() - t0:.2f}s): {reply}")
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
            reply = None
            agent_seconds = None
            error = None

            try:
                transcript = stt.run(utt)
                print(f"You ({transcript.seconds:.2f}s): {transcript.text}")

                t0 = time.time()
                reply = agent.ask(transcript.text)
                agent_seconds = time.time() - t0
                print(f"Jarvis ({agent_seconds:.2f}s): {reply}")

            except AgentError as exc:
                error = f"AgentError: {exc}"
                print(f"[agent error] {exc}")
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                print(f"[error] {exc}")

            recorder.log_turn(
                utt=utt,
                transcript=transcript,
                reply=reply,
                agent_seconds=agent_seconds,
                error=error,
            )

    except KeyboardInterrupt:
        print("\nBye.")


if __name__ == "__main__":
    main()