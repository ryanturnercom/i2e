"""Typed change broker for the console SSE channel.

The legacy ``serve._ChangeBroker`` emitted a single string per change
(a path), which forced the browser to do a full reload. The console
needs structured events keyed by ``kind`` so htmx can refresh only the
matching fragment:

    {"kind": "intent",  "slug": "capability-foo"}
    {"kind": "pending", "file": "2026-05-21-abc.yaml"}
    {"kind": "worker",  "slug": "capability-foo"}
    {"kind": "tick",    "tick_id": "2026-05-21-a8c4f3"}
    {"kind": "job",     "job_id": "regression-12-shipped"}

Each subscriber gets its own ``Queue``; the broker is thread-safe.
"""

from __future__ import annotations

import threading
from queue import Queue
from typing import Any, Literal

EventKind = Literal["intent", "pending", "worker", "tick", "job"]


class ChangeBroker:
    """Pub-sub fan-out for typed console change events."""

    def __init__(self) -> None:
        self._subs: list[Queue[dict[str, Any]]] = []
        self._lock = threading.Lock()

    def subscribe(self) -> Queue[dict[str, Any]]:
        """Register a new subscriber queue and return it."""
        q: Queue[dict[str, Any]] = Queue()
        with self._lock:
            self._subs.append(q)
        return q

    def unsubscribe(self, q: Queue[dict[str, Any]]) -> None:
        with self._lock:
            try:
                self._subs.remove(q)
            except ValueError:
                pass

    def notify(self, *, kind: EventKind, **payload: Any) -> None:
        """Emit a typed event to every subscriber.

        ``kind`` is a discriminator; the rest of the payload travels
        with it (slug / file / tick_id / job_id depending on kind).
        """
        event: dict[str, Any] = {"kind": kind, **payload}
        with self._lock:
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait(event)
            except Exception:
                pass

    def close(self) -> None:
        """Signal shutdown to every subscriber and drop them."""
        with self._lock:
            for q in list(self._subs):
                try:
                    q.put_nowait({"kind": "__shutdown__"})
                except Exception:
                    pass
            self._subs.clear()
