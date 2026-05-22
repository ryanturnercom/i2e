"""Console SSE broker must emit typed change events with a `kind` discriminator.

See .i2e/specs/i2e-console.md §3.3 (event model). The legacy serve.py
broker emitted a single string payload; the console needs structured
events so htmx can do targeted fragment swaps instead of full reloads.
"""

from __future__ import annotations

from i2e_core.console.sse import ChangeBroker


def test_typed_change_events():
    broker = ChangeBroker()
    q = broker.subscribe()
    try:
        broker.notify(kind="intent", slug="capability-foo")
        broker.notify(kind="pending", file="2026-05-21-abc.yaml")
        broker.notify(kind="worker", slug="capability-bar")
        broker.notify(kind="tick", tick_id="2026-05-21-a8c4f3")
        broker.notify(kind="job", job_id="regression-12-shipped")

        intent_event = q.get(timeout=1)
        assert intent_event == {"kind": "intent", "slug": "capability-foo"}

        pending_event = q.get(timeout=1)
        assert pending_event == {"kind": "pending", "file": "2026-05-21-abc.yaml"}

        worker_event = q.get(timeout=1)
        assert worker_event == {"kind": "worker", "slug": "capability-bar"}

        tick_event = q.get(timeout=1)
        assert tick_event == {"kind": "tick", "tick_id": "2026-05-21-a8c4f3"}

        job_event = q.get(timeout=1)
        assert job_event == {"kind": "job", "job_id": "regression-12-shipped"}
    finally:
        broker.close()
