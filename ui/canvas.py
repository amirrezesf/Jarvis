"""
PyQt6 black-canvas UI for Jarvis.

The UI runs on the main thread. A single worker thread runs the
mic -> transcription -> agent loop and communicates via Qt signals.
"""

from __future__ import annotations

import queue
import threading
import time

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class Worker(QObject):
    """Mic/STT/agent loop running off the main thread."""

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

    # ---- called from the UI thread -----------------------------------
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

    # ---- runs on the worker thread -----------------------------------
    def run(self) -> None:
        # Deferred imports so launch is fast and import errors are visible.
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
        except Exception as exc:
            self.error.emit(f"Init failed: {exc}")
            return

        # Recording is triggered by the outer loop's start_event, so
        # MicSource's own start_wait is a no-op. Only stop is waited on.
        mic = MicSource(
            start_wait=lambda: None,
            stop_wait=self._stop_event.wait,
        )

        self.status_changed.emit("Ready")

        while not self._should_quit:
            self._start_event.wait()
            self._start_event.clear()
            if self._should_quit:
                break

            # Text input has priority over mic.
            try:
                text = self._text_queue.get_nowait()
            except queue.Empty:
                text = None

            if text is not None:
                self.user_text.emit(text)
                self._run_agent(agent, recorder, None, None, text)
                self._stop_event.clear()
                continue

            # Mic path.
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

    # ------------------------------------------------------------------
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


class JarvisWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._recording = False

        self.setWindowTitle("Jarvis")
        self.resize(860, 640)

        central = QWidget()
        central.setStyleSheet("background-color: #000;")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Status line
        self.status_label = QLabel("Starting…")
        self.status_label.setStyleSheet(
            "color: #777; background-color: #000; "
            "padding: 8px 16px; font-family: monospace; font-size: 12px;"
        )
        layout.addWidget(self.status_label)

        # Conversation area
        self.conversation = QTextEdit()
        self.conversation.setReadOnly(True)
        self.conversation.setStyleSheet(
            "background-color: #000; color: #e0e0e0; "
            "border: none; padding: 16px;"
        )
        font = QFont("JetBrains Mono", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.conversation.setFont(font)
        layout.addWidget(self.conversation, stretch=1)

        # Bottom bar
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

        # Worker thread
        self.thread = QThread()
        self.worker = Worker()
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.status_changed.connect(self._on_status)
        self.worker.user_text.connect(self._on_user_text)
        self.worker.reply_started.connect(self._on_reply_started)
        self.worker.reply_chunk.connect(self._on_reply_chunk)
        self.worker.reply_finished.connect(self._on_reply_finished)
        self.worker.error.connect(self._on_error)

        self.thread.start()

    # ---- UI callbacks -------------------------------------------------
    def _on_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _on_user_text(self, text: str) -> None:
        self._append("\n\nYou: ", "#555")
        self._append(text, "#aaa")

    def _on_reply_started(self) -> None:
        self._append("\nJarvis: ", "#555")

    def _on_reply_chunk(self, chunk: str) -> None:
        self._append(chunk, "#e8e8e8")

    def _on_reply_finished(self) -> None:
        pass

    def _on_error(self, text: str) -> None:
        self._append(f"\n[error] {text}", "#f66")

    def _on_record_toggle(self) -> None:
        if not self._recording:
            self._recording = True
            self.record_btn.setText("Stop")
            self.worker.request_start_recording()
        else:
            self._recording = False
            self.record_btn.setText("Record")
            self.worker.request_stop_recording()

    def _on_text_submit(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.worker.request_text(text)

    def _append(self, text: str, color: str) -> None:
        cursor = self.conversation.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        cursor.insertText(text)
        self.conversation.setTextCursor(cursor)
        self.conversation.ensureCursorVisible()

    # ---- shutdown -----------------------------------------------------
    def closeEvent(self, event) -> None:
        self.worker.quit()
        self.thread.quit()
        self.thread.wait(2000)
        event.accept()


def run_ui() -> None:
    import sys

    app = QApplication(sys.argv)
    window = JarvisWindow()
    window.show()
    sys.exit(app.exec())