import sys
from audio.mic import MicSource
from core.transcriber import Transcriber
from core.agent import Agent

def main():
    agent = Agent()
    if "--text" in sys.argv:                # test agent without the mic
        while True:
            print("Jarvis:", agent.ask(input("You: ")))
    source, stt = MicSource(), Transcriber()
    print("Hold right ctrl and speak...")
    while True:
        utt = source.listen()
        if utt is None:
            continue
        tr = stt.run(utt)
        print(f"You ({tr.seconds:.2f}s): {tr.text}")
        print("Jarvis:", agent.ask(tr.text))

if __name__ == "__main__":
    main()