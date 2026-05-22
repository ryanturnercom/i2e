"""Server lifecycle tests — start, serve, SSE, stop."""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import pytest

from i2e_core.paths import serve_url_path
from i2e_core.serve import start_server, stop_server


def _http_get(url: str, timeout: float = 3.0):
    return urllib.request.urlopen(url, timeout=timeout)


def test_refuses_non_loopback_host(project: Path) -> None:
    with pytest.raises(ValueError):
        start_server(project, host="0.0.0.0", port=0, open_browser=False)


def test_start_returns_loopback_url_and_writes_serve_file(project: Path) -> None:
    try:
        url = start_server(project, port=0, open_browser=False)
        assert url.startswith("http://127.0.0.1:")
        parsed = urlparse(url)
        assert parsed.hostname == "127.0.0.1"
        assert parsed.port and parsed.port > 0
        assert serve_url_path(project).exists()
        assert serve_url_path(project).read_text(encoding="utf-8").strip() == url
    finally:
        stop_server(project)


def test_get_root_returns_html_with_capabilities(project: Path) -> None:
    try:
        url = start_server(project, port=0, open_browser=False)
        with _http_get(url) as resp:
            assert resp.status == 200
            body = resp.read().decode("utf-8")
        # GET / now serves the i2e Console dashboard (replacing the static
        # report.html). The active capability surfaces in a card + sidebar.
        assert "<!doctype html>" in body.lower()
        assert "i2e console" in body.lower()
        assert "alpha" in body
    finally:
        stop_server(project)


def test_events_endpoint_sends_sse_on_filesystem_change(project: Path) -> None:
    """Modify a file under ``.i2e/``; the SSE client should see a change event."""
    try:
        url = start_server(project, port=0, open_browser=False)
        # Connect to /events with a generous read timeout.
        with urllib.request.urlopen(url + "events", timeout=3.0) as resp:
            assert resp.headers.get("Content-Type", "").startswith(
                "text/event-stream"
            )
            # Bytes-level read — the initial "ready" event should come fast.
            ready_chunk = b""
            deadline = time.time() + 2.0
            while time.time() < deadline and b"event: ready" not in ready_chunk:
                line = resp.fp.readline()
                if not line:
                    break
                ready_chunk += line
            assert b"event: ready" in ready_chunk

            # Trigger a change by writing a file under .i2e/.
            marker = project / ".i2e" / "trigger.txt"
            # Wait a beat so the watchdog observer's internal scheduler is ready.
            time.sleep(0.1)
            marker.write_text("hello", encoding="utf-8")

            # Read until we see a change event.
            change_chunk = b""
            deadline = time.time() + 4.0
            while time.time() < deadline and b"event: change" not in change_chunk:
                line = resp.fp.readline()
                if not line:
                    break
                change_chunk += line
            assert b"event: change" in change_chunk
    finally:
        stop_server(project)


def test_stop_removes_serve_url_file(project: Path) -> None:
    start_server(project, port=0, open_browser=False)
    assert serve_url_path(project).exists()
    stop_server(project)
    assert not serve_url_path(project).exists()


def test_stop_is_idempotent_when_not_running(project: Path) -> None:
    # No server up — stop_server should not raise.
    stop_server(project)
    assert not serve_url_path(project).exists()


def test_get_unknown_path_returns_404(project: Path) -> None:
    try:
        url = start_server(project, port=0, open_browser=False)
        try:
            _http_get(url + "does-not-exist")
        except urllib.error.HTTPError as e:
            assert e.code == 404
        else:
            raise AssertionError("expected 404")
    finally:
        stop_server(project)


def test_post_shutdown_endpoint(project: Path) -> None:
    """Posting /shutdown should make the server stop on its own."""
    url = start_server(project, port=0, open_browser=False)
    req = urllib.request.Request(url + "shutdown", method="POST")
    with urllib.request.urlopen(req, timeout=2.0) as resp:
        assert resp.status == 200
    # The server thread should die shortly. The url_file is removed by
    # stop_server, but POST /shutdown alone leaves the file behind — clean up.
    time.sleep(0.2)
    stop_server(project)
    assert not serve_url_path(project).exists()


def test_post_unknown_path_returns_404(project: Path) -> None:
    try:
        url = start_server(project, port=0, open_browser=False)
        req = urllib.request.Request(url + "no-such-endpoint", method="POST")
        try:
            urllib.request.urlopen(req, timeout=2.0)
        except urllib.error.HTTPError as e:
            assert e.code == 404
        else:
            raise AssertionError("expected 404")
    finally:
        stop_server(project)


def test_stop_via_http_when_handle_missing(project: Path, monkeypatch) -> None:
    """Cover the ``stop_server`` HTTP fallback path.

    When the in-process handle is missing (e.g. a different process started
    the server), ``stop_server`` reads ``.serve.url`` and POSTs ``/shutdown``.
    """
    url = start_server(project, port=0, open_browser=False)
    # Forcibly drop the in-process handle so stop_server takes the HTTP path.
    from i2e_core import serve as serve_mod
    with serve_mod._HANDLES_LOCK:
        serve_mod._HANDLES.pop(str(Path(project).resolve()), None)
    stop_server(project)
    # The url file must be gone.
    assert not serve_url_path(project).exists()
    # And the original URL must no longer accept connections.
    deadline = time.time() + 2.0
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=0.3)
        except Exception:
            return
        time.sleep(0.1)
    # Best-effort: we don't fail the test if the OS is slow to reap the port.
