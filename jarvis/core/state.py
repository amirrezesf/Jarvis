"""
Pending instruction state.

Holds extracted instructions between the moment they're stated (T1) and
the moment a trigger fires (T2). Entries expire either when consumed by
a matching trigger or after a fixed TTL.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from jarvis import config
from jarvis.core.events import InstructionRecord

logger = logging.getLogger(__name__)


@dataclass
class _Entry:
    record: InstructionRecord
    created_at: datetime


class InstructionState:
    """Short-lived list of pending instructions with TTL expiry."""

    def __init__(self, ttl_seconds: int | None = None) -> None:
        self.ttl = (
            ttl_seconds if ttl_seconds is not None
            else config.INSTRUCTION_TTL_SECONDS
        )
        self._entries: list[_Entry] = []

    # ------------------------------------------------------------------
    def add(self, record: InstructionRecord) -> None:
        self._entries.append(
            _Entry(record=record, created_at=datetime.now())
        )
        logger.info(
            "State + %s/%s/%s conf=%.2f (pending=%d)",
            record.trigger_type, record.action, record.scope,
            record.confidence, len(self._entries),
        )

    # ------------------------------------------------------------------
    def expire(self) -> int:
        """Drop entries older than TTL. Returns the number removed."""
        cutoff = datetime.now() - timedelta(seconds=self.ttl)
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.created_at >= cutoff]
        removed = before - len(self._entries)
        if removed:
            logger.info(
                "State expired %d entries (pending=%d)",
                removed, len(self._entries),
            )
        return removed

    # ------------------------------------------------------------------
    def pop_matching_name_trigger(self) -> InstructionRecord | None:
        """Called when a name_called trigger fires.

        Returns the most recent pending instruction whose trigger_type
        is name_called, or None. The chosen entry is removed from state.
        """
        cutoff = datetime.now() - timedelta(seconds=self.ttl)
        fresh = [e for e in self._entries if e.created_at >= cutoff]
        matches = [
            e for e in fresh if e.record.trigger_type == "name_called"
        ]
        if not matches:
            return None

        matches.sort(key=lambda e: e.created_at, reverse=True)
        chosen = matches[0]
        self._entries.remove(chosen)
        logger.info(
            "State - consumed %s/%s/%s",
            chosen.record.trigger_type,
            chosen.record.action,
            chosen.record.scope,
        )
        return chosen.record

    # ------------------------------------------------------------------
    def pending(self) -> list[InstructionRecord]:
        """Return non-expired entries (read-only view)."""
        cutoff = datetime.now() - timedelta(seconds=self.ttl)
        return [
            e.record for e in self._entries if e.created_at >= cutoff
        ]