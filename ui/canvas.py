"""
PyQt6 black-canvas UI for Jarvis.

Two modes:
  - assistant mode (default): mic -> Whisper -> 9Router -> reply
  - listener mode (--listen-ui): loopback -> Whisper -> pipeline -> decisions

Both use the same window. The left panel shows transcript/chat, the right
panel shows decisions produced by the listener pipeline.
"""

from __future__ import annotations
import logging
import config
import queue
import threading
import time
from datetime import datetime
from typing import Any
from core.alarm import play as play_alarm
from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__) 
# ---------------------------------------------------------------------------
# Assistant worker
# ---------------------------------------------------------------------------
class Worker(QObject):
    status_changed = pyqtSignal(str)
    user_text = pyqtSignal(str)
    reply_started = pyqtSignal()
    reply_chunk = pyqtSignal(str)
    reply_finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._start_event = threading.Event()
        self._stop_event = threading.Event()
        self._should_quit = False
        self._text_queue: queue.Queue[str] = queue.Queue()

    def request_start_recording(self) -> None:
        self._start_event.set()

    def request_stop_recording(self) -> None:
        self._stop_event.set()

    def request_text(self, text: str) -> None:
        self._text_queue.put(text)
        self._start_event.set()

    def quit(self) -> None:
        self._should_quit = True
        self._start_event.set()
        self._stop_event.set()

    def run(self) -> None:
        try:
            from audio.mic import MicSource
            from core.agent import Agent
            from core.recorder import SessionRecorder
            from core.transcriber import Transcriber
        except Exception as exc:
            self.error.emit(f"Import failed: {exc}")
            return

        try:
            agent = Agent()
            stt = Transcriber()
            recorder = SessionRecorder()
            recorder.start_session(mode="assistant_ui")
        except Exception as exc:
            self.error.emit(f"Init failed: {exc}")
            return

        mic = MicSource(start_wait=lambda: None, stop_wait=self._stop_event.wait)
        self.status_changed.emit("Ready")

        while not self._should_quit:
            self._start_event.wait()
            self._start_event.clear()
            if self._should_quit:
                break

            try:
                text = self._text_queue.get_nowait()
            except queue.Empty:
                text = None

            if text is not None:
                self.user_text.emit(text)
                self._run_agent(agent, recorder, None, None, text)
                self._stop_event.clear()
                continue

            self.status_changed.emit("Recording")
            utt = mic.listen()
            self._stop_event.clear()
            if utt is None:
                self.status_changed.emit("Ready")
                continue

            self.status_changed.emit("Transcribing")
            try:
                transcript = stt.run(utt)
            except Exception as exc:
                self.error.emit(f"Transcribe error: {exc}")
                self.status_changed.emit("Ready")
                continue

            self.user_text.emit(transcript.text)
            self._run_agent(agent, recorder, utt, transcript, transcript.text)

        self.status_changed.emit("Stopped")

    def _run_agent(self, agent, recorder, utt, transcript, text) -> None:
        from core.agent import AgentError

        self.status_changed.emit("Thinking")
        self.reply_started.emit()

        t0 = time.time()
        first_token = None
        parts: list[str] = []
        error = None

        try:
            for chunk in agent.ask_stream(text):
                if first_token is None:
                    first_token = time.time() - t0
                parts.append(chunk)
                self.reply_chunk.emit(chunk)
        except AgentError as exc:
            error = f"AgentError: {exc}"
            self.error.emit(str(exc))
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self.error.emit(str(exc))

        agent_seconds = time.time() - t0
        self.reply_finished.emit()
        self.status_changed.emit("Ready")

        if recorder is not None and utt is not None:
            try:
                recorder.log_turn(
                    utt=utt,
                    transcript=transcript,
                    reply="".join(parts) or None,
                    agent_seconds=agent_seconds,
                    agent_first_token_seconds=first_token,
                    error=error,
                )
            except Exception as exc:
                self.error.emit(f"Log failed: {exc}")


# ---------------------------------------------------------------------------
# Listener worker
# ---------------------------------------------------------------------------
class ListenerWorker(QObject):
    status_changed = pyqtSignal(str)
    transcript = pyqtSignal(str, float)     # text, transcribe_seconds
    decision = pyqtSignal(str, str, str)    # action, args_str, reasoning
    error = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._should_quit = False

    def quit(self) -> None:
        self._should_quit = True

    def run(self) -> None:
        try:
            from audio.loopback import LoopbackSource
            from core.pipeline import ListenerPipeline
            from core.recorder import SessionRecorder
            from core.transcriber import Transcriber
        except Exception as exc:
            self.error.emit(f"Import failed: {exc}")
            return

        try:
            source = LoopbackSource()
            stt = Transcriber()
            pipeline = ListenerPipeline()
            recorder = SessionRecorder()
            session_id = recorder.start_session(mode="listener_ui")
        except Exception as exc:
            self.error.emit(f"Init failed: {exc}")
            return

        self.status_changed.emit(f"Listening  ({session_id})")

        while not self._should_quit:
            try:
                utt = source.listen()
            except Exception as exc:
                self.error.emit(f"Capture error: {exc}")
                break

            if utt is None:
                continue
            t0 = time.time()
            try:
                tr = stt.run(utt)
            except Exception as exc:
                self.error.emit(f"Transcribe error: {exc}")
                continue

            transcribe_wall = time.time() - t0
            self.transcript.emit(tr.text, tr.seconds)
            t1 = time.time()
            decisions = pipeline.feed(tr.text)

            pipeline_wall = time.time() - t1
            logger.info(
                "wall audio=%.2fs transcribe=%.2fs pipeline=%.2fs decisions=%d",
                len(utt.audio) / config.SAMPLE_RATE,
                transcribe_wall,
                pipeline_wall,
                len(decisions),
            )
            if decisions:
                play_alarm()

            for d in decisions:
                self.decision.emit(
                    d.action, _format_decision_args(d), d.reasoning
                )

            try:
                recorder.log_turn(
                    utt=utt,
                    transcript=tr,
                    reply=None,
                    agent_seconds=None,
                    extra={
                        "decisions": [
                            {
                                "action": d.action,
                                "args": d.args,
                                "trigger": d.trigger_evidence,
                                "score": d.trigger_score,
                                "instruction_source": d.instruction_source,
                                "scope": d.instruction_scope,
                                "confidence": d.instruction_confidence,
                                "reasoning": d.reasoning,
                            }
                            for d in decisions
                        ],
                    },
                )
            except Exception as exc:
                self.error.emit(f"Log failed: {exc}")

        self.status_changed.emit("Stopped")

def _format_decision_args(d) -> str:
    """Render a Decision's payload for the decisions panel."""
    lines: list[str] = []
    if d.action == "notify_me":
        text = str(d.args.get("text", "")).strip()
        if text:
            lines.append(f"Q:      {text}")
        if d.context_summary:
            lines.append(f"CTX:    {d.context_summary}")
    elif d.action == "type_number":
        lines.append(f"n = {d.args.get('n')}")
    elif d.action == "send_chat":
        lines.append(f"text = {d.args.get('text')}")
    else:
        lines.append(str(d.args))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------
class JarvisWindow(QMainWindow):
    def __init__(self, mode: str = "assistant") -> None:
        super().__init__()
        self._mode = mode
        self._recording = False

        self.setWindowTitle("Jarvis")
        self.resize(1180, 680)

        central = QWidget()
        central.setStyleSheet("background-color: #000;")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Status line.
        self.status_label = QLabel("Starting…")
        self.status_label.setStyleSheet(
            "color: #777; background-color: #000; "
            "padding: 8px 16px; font-family: monospace; font-size: 12px;"
        )
        layout.addWidget(self.status_label)

        # Splitter: conversation | decisions.
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(
            "QSplitter::handle { background-color: #1a1a1a; }"
        )

        self.conversation = QTextEdit()
        self.conversation.setReadOnly(True)
        self.conversation.setStyleSheet(
            "background-color: #000; color: #e0e0e0; "
            "border: none; padding: 16px;"
        )
        mono = QFont("JetBrains Mono", 11)
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.conversation.setFont(mono)
        splitter.addWidget(self.conversation)

        self.decisions = QTextEdit()
        self.decisions.setReadOnly(True)
        self.decisions.setStyleSheet(
            "background-color: #060606; color: #cfcfcf; "
            "border-left: 1px solid #1a1a1a; padding: 16px;"
        )
        self.decisions.setFont(mono)
        splitter.addWidget(self.decisions)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter, stretch=1)

        # Bottom bar (assistant mode only).
        if mode == "assistant":
            bottom = QWidget()
            bottom.setStyleSheet("background-color: #000;")
            bottom_layout = QHBoxLayout(bottom)
            bottom_layout.setContentsMargins(16, 8, 16, 16)
            bottom_layout.setSpacing(8)

            self.input = QLineEdit()
            self.input.setPlaceholderText("Type a message, or click Record")
            self.input.setStyleSheet(
                "background-color: #111; color: #eee; border: 1px solid #333; "
                "padding: 8px; font-family: monospace; font-size: 12px;"
            )
            self.input.returnPressed.connect(self._on_text_submit)
            bottom_layout.addWidget(self.input, stretch=1)

            self.record_btn = QPushButton("Record")
            self.record_btn.setStyleSheet(
                "QPushButton { background-color: #222; color: #eee; "
                "border: 1px solid #444; padding: 8px 20px; "
                "font-family: monospace; font-size: 12px; } "
                "QPushButton:hover { background-color: #333; } "
                "QPushButton:pressed { background-color: #444; }"
            )
            self.record_btn.clicked.connect(self._on_record_toggle)
            bottom_layout.addWidget(self.record_btn)

            layout.addWidget(bottom)

        self.setCentralWidget(central)

        # Worker + thread. Note: the attribute is not named `thread`
        # because QObject already defines a `thread()` method.
        self.worker_thread = QThread()
        if mode == "listener":
            listener: ListenerWorker = ListenerWorker()
            listener.moveToThread(self.worker_thread)
            listener.status_changed.connect(self._on_status)
            listener.transcript.connect(self._on_listener_transcript)   # type: ignore[attr-defined]
            listener.decision.connect(self._on_decision)                # type: ignore[attr-defined]
            listener.error.connect(self._on_error)
            self.worker: Any = listener
        else:
            assistant: Worker = Worker()
            assistant.moveToThread(self.worker_thread)
            assistant.status_changed.connect(self._on_status)
            assistant.user_text.connect(self._on_user_text)             # type: ignore[attr-defined]
            assistant.reply_started.connect(self._on_reply_started)     # type: ignore[attr-defined]
            assistant.reply_chunk.connect(self._on_reply_chunk)         # type: ignore[attr-defined]
            assistant.reply_finished.connect(self._on_reply_finished)   # type: ignore[attr-defined]
            assistant.error.connect(self._on_error)
            self.worker = assistant

        self.worker_thread.started.connect(self.worker.run)
        self.worker_thread.start()

    # ---- UI callbacks -------------------------------------------------
    def _on_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _on_user_text(self, text: str) -> None:
        self._append(self.conversation, "\n\nYou: ", "#555")
        self._append(self.conversation, text, "#aaa")

    def _on_reply_started(self) -> None:
        self._append(self.conversation, "\nJarvis: ", "#555")

    def _on_reply_chunk(self, chunk: str) -> None:
        self._append(self.conversation, chunk, "#e8e8e8")

    def _on_reply_finished(self) -> None:
        pass

    def _on_listener_transcript(self, text: str, seconds: float) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self._append(
            self.conversation, f"\n[{stamp} {seconds:.1f}s] ", "#444"
        )
        self._append(self.conversation, text, "#c0c0c0")

    def _on_decision(self, action: str, args: str, reasoning: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self._append(self.decisions, f"\n[{stamp}]\n", "#555")
        self._append(self.decisions, f"ACTION: {action}\n", "#7fd67f")
        self._append(self.decisions, args + "\n", "#e0e0e0")
        self._append(self.decisions, f"WHY:    {reasoning}\n", "#888")

    def _on_error(self, text: str) -> None:
        self._append(self.conversation, f"\n[error] {text}", "#f66")

    def _on_record_toggle(self) -> None:
        if self._mode != "assistant":
            return
        if not self._recording:
            self._recording = True
            self.record_btn.setText("Stop")
            self.worker.request_start_recording()
        else:
            self._recording = False
            self.record_btn.setText("Record")
            self.worker.request_stop_recording()

    def _on_text_submit(self) -> None:
        if self._mode != "assistant":
            return
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.worker.request_text(text)

    def _append(self, widget: QTextEdit, text: str, color: str) -> None:
        cursor = widget.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        cursor.insertText(text)
        widget.setTextCursor(cursor)
        widget.ensureCursorVisible()

    # ---- shutdown -----------------------------------------------------
    def closeEvent(self, a0) -> None:
        self.worker.quit()
        self.worker_thread.quit()
        self.worker_thread.wait(2000)
        if a0 is not None:
            a0.accept()


def run_ui(mode: str = "assistant") -> None:
    import sys

    app = QApplication(sys.argv)
    window = JarvisWindow(mode=mode)
    window.show()
    sys.exit(app.exec())


def run_listener_ui() -> None:
    run_ui(mode="listener")