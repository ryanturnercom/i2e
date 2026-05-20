"""Tests for the serve-no-self-refresh-loop capability.

The SSE live-reload path used to feed itself: every ``GET /`` re-rendered
``report.html``, the watchdog saw the write, and the broker fired a
``change`` event that triggered the next ``GET /``. This file exercises
the filter that stops that loop, plus the two preserved behaviours
(ready event on connect, debounce window).
"""

from __future__ import annotations

import textwrap
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pytest

from i2e_core import serve
from i2e_core.evidence import CurrentEvidence, ItemVerdict, write_current
from i2e_core.paths import report_path
from i2e_core.report import render
from i2e_core.serve import _DEBOUNCE_SECONDS, start_server, stop_server


_INTENT = """---
capability: {name}
created: 2026-05-19
updated: 2026-05-19
version: 1
status: active
watcher: '@me'
---

# {name}

## Evidence of success

- id: case-a
  type: case
  provider: pytest
  query: q
  expect: passes
  effort: medium

## Constraints

"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    for sub in ("context", "intents", "evidence", "pending", "logs"):
        (tmp_path / ".i2e" / sub).mkdir(parents=True, exist_ok=True)
    (tmp_path / ".i2e" / "intents" / "alpha.md").write_text(
        textwrap.dedent(_INTENT.format(name="alpha")), encoding="utf-8"
    )
    write_current(
        tmp_path,
        CurrentEvidence(
            capability="alpha",
            last_run="2026-05-19-aaa000",
            intent_version=1,
            items={
                "case-a": ItemVerdict(
                    verdict="pass",
                    attempts_used=0,
                    last_observed=datetime.now(timezone.utc),
                )
            },
        ),
    )
    return tmp_path


def _broker_for(project: Path):
    handle = serve._HANDLES[str(Path(project).resolve())]
    return handle.broker


def _drain(q, deadline: float) -> list[str]:
    """Pull every message available before ``deadline`` (wall clock)."""
    msgs: list[str] = []
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        try:
            msgs.append(q.get(timeout=remaining))
        except Exception:
            break
    return msgs


def test_single_get_root_emits_no_change_event(project: Path) -> None:
    try:
        url = start_server(project)
        broker = _broker_for(project)
        # Subscribe BEFORE the GET so we'd see any event the watcher emits.
        q = broker.subscribe()
        # Give watchdog a moment to settle.
        time.sleep(0.1)

        with urllib.request.urlopen(url, timeout=3.0) as resp:
            resp.read()

        # GET / re-renders report.html (and a sibling report.html.tmp from
        # atomic_write). Both must be filtered — no change event should fire.
        msgs = _drain(q, deadline=time.time() + _DEBOUNCE_SECONDS + 0.6)
        relevant = [m for m in msgs if m and m != "__shutdown__"]
        assert relevant == [], f"expected silence; got {relevant!r}"
    finally:
        stop_server(project)


def test_intent_file_write_emits_change_event(project: Path) -> None:
    try:
        start_server(project)
        broker = _broker_for(project)
        q = broker.subscribe()
        # Give watchdog a beat to register the schedule.
        time.sleep(0.2)

        intent_file = project / ".i2e" / "intents" / "alpha.md"
        intent_file.write_text(
            intent_file.read_text(encoding="utf-8") + "\n",
            encoding="utf-8",
        )

        # A real user edit MUST flow through to the broker.
        msg = q.get(timeout=3.0)
        assert msg
        assert "alpha.md" in msg
    finally:
        stop_server(project)


def test_render_writing_report_html_emits_no_change_event(
    project: Path,
) -> None:
    try:
        start_server(project)
        broker = _broker_for(project)
        q = broker.subscribe()
        time.sleep(0.2)

        # Drive render directly (bypassing HTTP) — the path the old loop
        # used to ride. The fix must filter the report.html write so this
        # is a no-op for SSE subscribers.
        render(project)
        # Confirm we actually wrote the file the watcher could have seen.
        assert report_path(project).exists()

        msgs = _drain(q, deadline=time.time() + _DEBOUNCE_SECONDS + 0.6)
        relevant = [m for m in msgs if m and m != "__shutdown__"]
        assert relevant == [], f"expected silence; got {relevant!r}"
    finally:
        stop_server(project)


def test_ready_event_and_debounce_window_unchanged(project: Path) -> None:
    # The debounce constant must remain 200ms — anything else changes the
    # perceived latency and is explicitly out of scope.
    assert _DEBOUNCE_SECONDS == 0.2

    try:
        url = start_server(project)
        # Connect briefly and confirm the immediate "ready" event still
        # arrives before any change activity.
        chunks: list[bytes] = []
        seen_ready = threading.Event()

        def _reader() -> None:
            try:
                with urllib.request.urlopen(
                    url + "events", timeout=3.0
                ) as resp:
                    deadline = time.time() + 2.5
                    while time.time() < deadline and not seen_ready.is_set():
                        line = resp.fp.readline()
                        if not line:
                            break
                        chunks.append(line)
                        if b"event: ready" in b"".join(chunks):
                            seen_ready.set()
                            break
            except Exception:
                pass

        t = threading.Thread(target=_reader, daemon=True)
        t.start()
        t.join(timeout=3.0)
        assert seen_ready.is_set(), (
            f"never saw ready event; got: {b''.join(chunks)!r}"
        )
    finally:
        stop_server(project)
