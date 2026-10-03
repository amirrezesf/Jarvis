"""
Headless listener.

Runs the full listener pipeline — loopback audio -> VAD -> Whisper ->
extraction -> trigger detection -> decisions — and hands Decision
objects to a caller-supplied callback.

No UI, no PyQt, no executor. This is the interface SkyroomBot imports.

The caller decides what to do with each decision:
  - Standalone Jarvis UI wraps this and routes decisions through its
    Executor (dry-run backend).
  - SkyroomBot wraps this and routes decisions through its own executor
    that talks to the Selenium driver.

Threading model: one worker thread, started by start(), joined by stop().
Callbacks fire on that worker thread. The caller is responsible for
marshalling to whatever thread it needs (e.g. Qt signals).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

from jarvis.core.alarm import play as play_alarm
from jarvis.core.context import StudentContext
from jarvis.core.events import Decision
from jarvis.core.pipeline import ListenerPipeline
from jarvis.core.recorder import SessionRecorder
from jarvis.core.transcriber import Transcriber

logger = logging.getLogger(__name__)


DecisionCallback = Callable[[Decision], None]
TranscriptCallback = Callable[[str, float], None]
ErrorCallback = Callable[[str], None]


class Listener:
    """Headless listener pipeline.

    Usage:
        listener = Listener(
            context=StudentContext.from_user(user_dict),
            on_decision=lambda d: handle(d),
        )
        listener.start()
        ...
        listener.stop()
    """

    def __init__(
        self,
        context: StudentContext,
        on_decision: DecisionCallback,
        on_transcript: Optional[TranscriptCallback] = None,
        on_error: Optional[ErrorCallback] = None,
        on_ready: Optional[Callable[[], None]] = None,
        alarm: bool = True,
        session_mode: str = "listener",
    ) -> None:
        self.context = context
        self.on_decision = on_decision
        self.on_transcript = on_transcript
        self.on_error = on_error
        self.on_ready = on_ready
        self.alarm = alarm
        self.session_mode = session_mode

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._started = threading.Event()
        self._running = False

    # ------------------------------------------------------------------
    @property
    def running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    def start(self, wait: float = 0.0) -> None:
        """Spawn the worker thread.

        If wait > 0, block up to `wait` seconds for initialization to
        complete (or fail). Default is non-blocking — the caller learns
        about success via on_ready and about failure via on_error.
        """
        if self._thread is not None and self._thread.is_alive():
            logger.warning("Listener already running")
            return

        self._stop_event.clear()
        self._started.clear()
        self._thread = threading.Thread(
            target=self._run, name="jarvis-listener", daemon=True,
        )
        self._thread.start()
        if wait > 0:
            self._started.wait(timeout=wait)

    # ------------------------------------------------------------------
    def stop(self, timeout: float = 5.0) -> None:
        """Signal the worker to stop and join it."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("Listener thread did not stop within %.1fs", timeout)
        self._running = False

    # ------------------------------------------------------------------
    def _emit_error(self, msg: str) -> None:
        logger.error(msg)
        if self.on_error is not None:
            try:
                self.on_error(msg)
            except Exception:
                logger.exception("on_error callback raised")

    # ------------------------------------------------------------------
    def _run(self) -> None:
        # Deferred imports so import-time errors are reported to the caller.
        try:
            from jarvis.audio.loopback import LoopbackSource
        except Exception as exc:
            self._emit_error(f"Import failed: {exc}")
            self._started.set()
            return

        try:
            source = LoopbackSource()
            stt = Transcriber()
            pipeline = ListenerPipeline(context=self.context)
            recorder = SessionRecorder()
            session_id = recorder.start_session(mode=self.session_mode)
        except Exception as exc:
            self._emit_error(f"Init failed: {exc}")
            self._started.set()
            return

        self._running = True
        self._started.set()
        logger.info(
            "Listener started  session=%s  user=%s",
            session_id, self.context.user_name,
        )

        try:
            while not self._stop_event.is_set():
                try:
                    utt = source.listen()
                except Exception as exc:
                    self._emit_error(f"Capture error: {exc}")
                    break

                if utt is None:
                    continue
                if self._stop_event.is_set():
                    break

                try:
                    tr = stt.run(utt)
                except Exception as exc:
                    self._emit_error(f"Transcribe error: {exc}")
                    continue

                if self.on_transcript is not None:
                    try:
                        self.on_transcript(tr.text, tr.seconds)
                    except Exception:
                        logger.exception("on_transcript callback raised")

                try:
                    decisions = pipeline.feed(tr.text)
                except Exception as exc:
                    self._emit_error(f"Pipeline error: {exc}")
                    decisions = []

                if decisions and self.alarm and  any(d.action == "notify_me" for d in decisions):
                    try:
                        play_alarm()
                    except Exception:
                        logger.exception("Alarm failed")

                for d in decisions:
                    try:
                        self.on_decision(d)
                    except Exception:
                        logger.exception("on_decision callback raised")

                try:
                    recorder.log_turn(
                        utt=utt,
                        transcript=tr,
                        reply=None,
                        agent_seconds=None,
                        extra={"decisions_count": len(decisions)},
                    )
                except Exception as exc:
                    logger.warning("Log failed: %s", exc)
        finally:
            try:
                source.close()
            except Exception:
                pass
            self._running = False
            logger.info("Listener stopped  session=%s", session_id)