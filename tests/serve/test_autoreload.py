"""Auto-reload — the serve server restarts itself on i2e_core code changes.

Covers the ``serve-autoreload`` capability: an opt-in watch over the
running package, a debounced re-exec on ``.py`` changes, and ``no-store``
static assets so CSS/JS edits never need a restart at all.
"""

from __future__ import annotations

import time
from pathlib import Path

from i2e_core import serve as serve_mod
from i2e_core.console.app import handle
from i2e_core.serve import _HANDLES, code_watch_dir, start_server, stop_server


def test_autoreload_watches_code_dir(project: Path, monkeypatch) -> None:
    """With autoreload on, the server also watches the i2e_core package."""
    # Belt-and-suspenders: a stray .py touch must never re-exec the test run.
    monkeypatch.setattr(serve_mod, "_restart", lambda *a, **k: None)

    try:
        start_server(project, port=0, open_browser=False, autoreload=True)
        handle_ = _HANDLES[str(project.resolve())]
        assert handle_.code_watch_dir == code_watch_dir()
    finally:
        stop_server(project)

    # Off by default — no code watch is scheduled.
    try:
        start_server(project, port=0, open_browser=False, autoreload=False)
        handle_ = _HANDLES[str(project.resolve())]
        assert handle_.code_watch_dir is None
    finally:
        stop_server(project)


def test_code_change_triggers_reexec(monkeypatch) -> None:
    """A debounced burst of .py writes drives exactly one restart."""
    calls: list[object] = []
    monkeypatch.setattr(
        serve_mod, "_restart", lambda server: calls.append(server)
    )

    handler = serve_mod._CodeReloadHandler(object(), debounce=0.05)

    class _Event:
        is_directory = False

        def __init__(self, path: str) -> None:
            self.src_path = path

    # A burst of source writes coalesces into a single restart.
    handler.on_modified(_Event("src/i2e_core/console/shell.py"))
    handler.on_created(_Event("src/i2e_core/console/prefs.py"))
    time.sleep(0.25)
    assert len(calls) == 1

    # A non-.py change (e.g. a static asset) is ignored.
    calls.clear()
    handler.on_modified(_Event("src/i2e_core/console/static/console.css"))
    time.sleep(0.25)
    assert calls == []


def test_static_assets_served_no_store(project: Path) -> None:
    """/static/* carries Cache-Control: no-store so edits show on a refresh."""
    resp = handle(project, "GET", "/static/console.css", "", "", None)
    assert resp.status == 200
    cache = resp.headers.get("Cache-Control", "")
    assert cache == "no-store"
    assert "max-age" not in cache
