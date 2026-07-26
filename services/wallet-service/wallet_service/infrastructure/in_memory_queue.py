"""Provide a process-local paper queue with no network transport."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable

from wallet_service.application import SignalQueue
from wallet_service.domain import PaperSignal


class InMemorySignalQueue(SignalQueue):
    """A deterministic FIFO adapter for paper assembly and tests."""

    def __init__(self, messages: Iterable[PaperSignal] = ()) -> None:
        self._messages = deque(messages)

    def publish(self, message: PaperSignal) -> None:
        """Append one already-validated paper signal."""
        self._messages.append(message)

    def receive(self) -> PaperSignal | None:
        """Return the next queued signal without blocking."""
        return None if not self._messages else self._messages.popleft()
