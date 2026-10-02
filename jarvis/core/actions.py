"""
Action execution.

Takes a Decision and produces an effect through a Backend. Actions listed
in config.ACTION_REQUIRE_CONFIRM go into a pending queue; everything else
executes immediately.

notify_me is intentionally not handled here — the UI already surfaces it,
and adding a desktop notification is the UI's job. This module only deals
with actions that have real side effects (type_number, send_chat).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable

from jarvis import config
from jarvis.core.events import Decision

logger = logging.getLogger(__name__)


class ActionError(Exception):
    """Raised when an action fails to execute."""


# ---------------------------------------------------------------------------
# Backend interface
# ---------------------------------------------------------------------------
class ActionBackend(ABC):
    """Where actions actually go.

    v1 ships DryRunBackend only. A SkyroomBackend will implement the same
    interface later, receiving the Selenium driver from SkyroomBot.
    """

    @abstractmethod
    def type_number(self, n: int) -> None: ...

    @abstractmethod
    def send_chat(self, text: str) -> None: ...


class DryRunBackend(ActionBackend):
    """Logs what would happen. No side effects."""

    def __init__(self) -> None:
        self.executed: list[tuple[str, dict]] = []

    def _record(self, action: str, args: dict) -> None:
        self.executed.append((action, args))
        logger.info("DRY-RUN  %s  args=%s", action, args)

    def type_number(self, n: int) -> None:
        self._record("type_number", {"n": n})

    def send_chat(self, text: str) -> None:
        self._record("send_chat", {"text": text})


# ---------------------------------------------------------------------------
# Outcomes and pending state
# ---------------------------------------------------------------------------
class Outcome(str, Enum):
    EXECUTED = "executed"
    PENDING = "pending"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class PendingAction:
    id: int
    decision: Decision
    created_at: datetime = field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------
class Executor:
    """Turns Decisions into actions.

    Actions listed in config.ACTION_REQUIRE_CONFIRM go into a pending
    queue. Everything else executes immediately. notify_me is skipped
    entirely — that decision type is handled by the UI.
    """

    EXECUTABLE = {"type_number", "send_chat"}

    def __init__(
        self,
        backend: ActionBackend | None = None,
        on_execute: Callable[[Decision, Outcome], None] | None = None,
    ) -> None:
        self.backend = backend or DryRunBackend()
        self.on_execute = on_execute
        self._pending: list[PendingAction] = []
        self._next_id = 1

    # ------------------------------------------------------------------
    def submit(self, decision: Decision) -> Outcome:
        action = decision.action

        if action not in self.EXECUTABLE:
            return Outcome.SKIPPED

        if action in config.ACTION_DISABLED:
            logger.info("Action disabled, skipping: %s", action)
            return Outcome.SKIPPED

        if not config.ACTION_EXECUTION_ENABLED:
            logger.info("Execution disabled, skipping: %s", action)
            return Outcome.SKIPPED

        if action in config.ACTION_REQUIRE_CONFIRM:
            pending = PendingAction(id=self._next_id, decision=decision)
            self._next_id += 1
            self._pending.append(pending)
            logger.info(
                "Action queued for confirmation: id=%d action=%s",
                pending.id, action,
            )
            return Outcome.PENDING

        return self._execute(decision)

    # ------------------------------------------------------------------
    def approve(self, action_id: int) -> Outcome:
        for i, p in enumerate(self._pending):
            if p.id == action_id:
                del self._pending[i]
                logger.info("Action approved: id=%d", action_id)
                return self._execute(p.decision)
        logger.warning("approve: unknown action id %d", action_id)
        return Outcome.SKIPPED

    def dismiss(self, action_id: int) -> None:
        for i, p in enumerate(self._pending):
            if p.id == action_id:
                del self._pending[i]
                logger.info("Action dismissed: id=%d", action_id)
                return
        logger.warning("dismiss: unknown action id %d", action_id)

    def pending(self) -> list[PendingAction]:
        return list(self._pending)

    # ------------------------------------------------------------------
    def _execute(self, decision: Decision) -> Outcome:
        action = decision.action
        args = decision.args
        try:
            if action == "type_number":
                n = int(args.get("n", 0))
                self.backend.type_number(n)
            elif action == "send_chat":
                text = str(args.get("text", ""))
                self.backend.send_chat(text)
            else:
                logger.warning("Unexpected action in executor: %r", action)
                return Outcome.SKIPPED
        except ActionError as exc:
            logger.error("Action %s failed: %s", action, exc)
            if self.on_execute:
                self.on_execute(decision, Outcome.FAILED)
            return Outcome.FAILED

        if self.on_execute:
            self.on_execute(decision, Outcome.EXECUTED)
        return Outcome.EXECUTED