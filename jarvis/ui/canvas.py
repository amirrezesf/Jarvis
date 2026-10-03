"""
PyQt6 black-canvas UI for Jarvis.

Two modes:
  - assistant mode: mic -> Whisper -> 9Router -> reply
  - listener mode:  loopback -> Whisper -> pipeline -> decisions -> executor

Listener mode delegates the pipeline to jarvis.core.listener.Listener
(headless), which runs its own worker thread and calls back via plain
Python callbacks. The callbacks emit Qt signals on a bridge object,
which Qt marshals to the main thread.
"""

from __future__ import annotations

import queue
import threading
import time
from datetime import datetime
from typing import Any

from PyQt6.QtCore import QObject, QThread, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QPushButton, QSplitter, QSystemTrayIcon, QTextEdit,
    QVBoxLayout, QWidget,
)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def _format_decision_args(d) -> str:
    lines: list[str] = []
    if d.action == "notify_me":
        text = str(d.args.get("text", "")).strip()
        if text:
            lines.append(f"Q:      {text}")
        if getattr(d, "context_summary", ""):
            lines.append(f"CTX:    {d.context_summary}")
    elif d.action == "type_number":
        lines.append(f"n = {d.args.get('n')}")
    elif d.action == "send_chat":
        lines.append(f"text = {d.args.get('text')}")
    else:
        lines.append(str(d.args))
    return "\n".join(lines)


def _format_pending(d) -> str:
    if d.action == "type_number":
        return f"type_number  n = {d.args.get('n')}"
    if d.action == "send_chat":
        return f"send_chat    \"{d.args.get('text')}\""
    return f"{d.action}  {d.args}"


# ---------------------------------------------------------------------------
# Assistant worker (unchanged)
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
            from jarvis.audio.mic import MicSource
            from jarvis.core.agent import Agent
            from jarvis.core.recorder import SessionRecorder
            from jarvis.core.transcriber import Transcriber
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
        from jarvis.core.agent import AgentError

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
# Listener bridge — signals only, no logic
# ---------------------------------------------------------------------------
class ListenerBridge(QObject):
    status_changed = pyqtSignal(str)
    transcript = pyqtSignal(str, float)     # text, seconds
    decision = pyqtSignal(str, str, str)    # action, formatted args, reasoning
    pending_added = pyqtSignal(int, str)    # action_id, description
    pending_removed = pyqtSignal(int)
    notify = pyqtSignal(str, str)           # title, text
    error = pyqtSignal(str)
    # The Listener calls back on its own thread; emit this so the Executor
    # work happens on the main thread via a queued connection.
    decision_ready = pyqtSignal(object)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class JarvisWindow(QMainWindow):
    def __init__(self, mode: str = "assistant") -> None:
        super().__init__()
        self._mode = mode
        self._recording = False
        self._pending_ids: list[int] = []
        self.executor: Any = None
        self.listener: Any = None

        self.setWindowTitle("Jarvis")
        self.resize(1180, 720)

        central = QWidget()
        central.setStyleSheet("background-color: #000;")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.status_label = QLabel("Starting…")
        self.status_label.setStyleSheet(
            "color: #777; background-color: #000; "
            "padding: 8px 16px; font-family: monospace; font-size: 12px;"
        )
        layout.addWidget(self.status_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background-color: #1a1a1a; }")

        self.conversation = QTextEdit()
        self.conversation.setReadOnly(True)
        self.conversation.setStyleSheet(
            "background-color: #000; color: #e0e0e0; border: none; padding: 16px;"
        )
        mono = QFont("JetBrains Mono", 11)
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.conversation.setFont(mono)
        splitter.addWidget(self.conversation)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.decisions = QTextEdit()
        self.decisions.setReadOnly(True)
        self.decisions.setStyleSheet(
            "background-color: #060606; color: #cfcfcf; "
            "border-left: 1px solid #1a1a1a; padding: 16px;"
        )
        self.decisions.setFont(mono)
        right_layout.addWidget(self.decisions, stretch=3)

        self.pending_header = QLabel("Pending confirmations")
        self.pending_header.setStyleSheet(
            "color: #888; background-color: #0a0a0a; "
            "padding: 6px 12px; font-family: monospace; font-size: 11px; "
            "border-top: 1px solid #1a1a1a;"
        )
        right_layout.addWidget(self.pending_header)

        self.pending_view = QTextEdit()
        self.pending_view.setReadOnly(True)
        self.pending_view.setStyleSheet(
            "background-color: #0a0a0a; color: #ffd166; "
            "border: none; padding: 12px;"
        )
        self.pending_view.setFont(mono)
        right_layout.addWidget(self.pending_view, stretch=1)

        hint = QLabel("Enter to approve top · Esc to dismiss top")
        hint.setStyleSheet(
            "color: #555; background-color: #0a0a0a; "
            "padding: 4px 12px; font-family: monospace; font-size: 10px;"
        )
        right_layout.addWidget(hint)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, stretch=1)

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

        self._tray: QSystemTrayIcon | None = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray = QSystemTrayIcon(self)
            self._tray.setToolTip("Jarvis")
            self._tray.show()

        self.worker: Any = None
        self.worker_thread: QThread | None = None
        self.bridge: ListenerBridge | None = None

        if mode == "listener":
            self._setup_listener_mode()
        else:
            self._setup_assistant_mode()

    # ------------------------------------------------------------------
    # Assistant mode
    # ------------------------------------------------------------------
    def _setup_assistant_mode(self) -> None:
        self.worker_thread = QThread()
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

    # ------------------------------------------------------------------
    # Listener mode
    # ------------------------------------------------------------------
    def _setup_listener_mode(self) -> None:
        from jarvis.core.actions import Executor

        self.executor = Executor()

        self.bridge = ListenerBridge()
        self.bridge.status_changed.connect(self._on_status)
        self.bridge.transcript.connect(self._on_listener_transcript)   # type: ignore[attr-defined]
        self.bridge.decision.connect(self._on_decision)                # type: ignore[attr-defined]
        self.bridge.pending_added.connect(self._on_pending_added)      # type: ignore[attr-defined]
        self.bridge.pending_removed.connect(self._on_pending_removed)  # type: ignore[attr-defined]
        self.bridge.notify.connect(self._on_notify)                    # type: ignore[attr-defined]
        self.bridge.error.connect(self._on_error)
        # Run the decision handler on the main thread even though the signal
        # is emitted from the Listener's worker thread.
        self.bridge.decision_ready.connect(self._process_decision)     # type: ignore[attr-defined]

        # Defer so the window is fully shown before the model starts loading.
        QTimer.singleShot(100, self._start_listener)

    def _start_listener(self) -> None:
        from jarvis.core.context import StudentContext
        from jarvis.core.listener import Listener

        assert self.bridge is not None
        ctx = StudentContext.from_config()
        self.bridge.status_changed.emit(f"Starting listener — {ctx.user_name}")

        self.listener = Listener(
            context=ctx,
            on_decision=self.bridge.decision_ready.emit,               # type: ignore[attr-defined]
            on_transcript=lambda t, s: self.bridge.transcript.emit(t, s),   # type: ignore[attr-defined]
            on_error=lambda e: self.bridge.error.emit(e),              # type: ignore[attr-defined]
            on_ready=lambda: self.bridge.status_changed.emit(          # type: ignore[attr-defined]
                f"Listening — {ctx.user_name}"
            ),
            alarm=True,
        )
        # Non-blocking: model load happens on the listener's thread.
        self.listener.start(wait=0.0)

    def _process_decision(self, d) -> None:
        """Runs on the main thread. Routes a Decision through the Executor."""
        from jarvis.core.actions import Outcome

        assert self.bridge is not None

        if d.action == "notify_me":
            self.bridge.notify.emit("Jarvis", _format_decision_args(d))
            self.bridge.decision.emit(d.action, _format_decision_args(d), d.reasoning)
            return

        outcome = self.executor.submit(d)
        if outcome == Outcome.PENDING:
            pending = self.executor.pending()
            if pending:
                pid = pending[-1].id
                self.bridge.pending_added.emit(pid, _format_pending(d))
            self.bridge.decision.emit(
                d.action, _format_decision_args(d),
                f"{d.reasoning}  [queued for confirmation]",
            )
        elif outcome == Outcome.EXECUTED:
            self.bridge.decision.emit(
                d.action, _format_decision_args(d),
                f"{d.reasoning}  [DRY-RUN executed]",
            )
        else:
            self.bridge.decision.emit(
                d.action, _format_decision_args(d),
                f"{d.reasoning}  [{outcome.value}]",
            )

    def _approve_top(self) -> None:
        if not self._pending_ids:
            return
        pid = self._pending_ids[0]
        outcome = self.executor.approve(pid)
        self._on_pending_removed(pid)
        if self.bridge is not None:
            self.bridge.status_changed.emit(f"Approved id={pid} ({outcome.value})")

    def _dismiss_top(self) -> None:
        if not self._pending_ids:
            return
        pid = self._pending_ids[0]
        self.executor.dismiss(pid)
        self._on_pending_removed(pid)
        if self.bridge is not None:
            self.bridge.status_changed.emit(f"Dismissed id={pid}")

    # ------------------------------------------------------------------
    # UI callbacks
    # ------------------------------------------------------------------
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
        self._append(self.conversation, f"\n[{stamp} {seconds:.1f}s] ", "#444")
        self._append(self.conversation, text, "#c0c0c0")

    def _on_decision(self, action: str, args: str, reasoning: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self._append(self.decisions, f"\n[{stamp}]\n", "#555")
        self._append(self.decisions, f"ACTION: {action}\n", "#7fd67f")
        self._append(self.decisions, args + "\n", "#e0e0e0")
        self._append(self.decisions, f"WHY:    {reasoning}\n", "#888")

    def _on_pending_added(self, action_id: int, description: str) -> None:
        self._pending_ids.append(action_id)
        self._render_pending()

    def _on_pending_removed(self, action_id: int) -> None:
        if action_id in self._pending_ids:
            self._pending_ids.remove(action_id)
        self._render_pending()

    def _render_pending(self) -> None:
        self.pending_view.clear()
        if not self._pending_ids:
            self.pending_header.setText("Pending confirmations  (none)")
            return
        self.pending_header.setText(
            f"Pending confirmations  ({len(self._pending_ids)})"
        )
        for i, pid in enumerate(self._pending_ids):
            prefix = "▶ " if i == 0 else "  "
            self._append(self.pending_view, f"{prefix}id={pid}\n", "#ffd166")

    def _on_notify(self, title: str, text: str) -> None:
        if self._tray is not None:
            self._tray.showMessage(
                title, text, QSystemTrayIcon.MessageIcon.Information, 8000,
            )

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

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------
    def keyPressEvent(self, a0) -> None:
        if a0 is None:
            return
        if self._mode == "listener" and self._pending_ids:
            if a0.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._approve_top()
                return
            if a0.key() == Qt.Key.Key_Escape:
                self._dismiss_top()
                return
        super().keyPressEvent(a0)

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------
    def closeEvent(self, a0) -> None:
        if self._mode == "listener" and self.listener is not None:
            self.listener.stop(timeout=5.0)
        if self.worker is not None:
            self.worker.quit()
        if self.worker_thread is not None:
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