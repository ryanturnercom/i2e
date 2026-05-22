"""Evidence for the ``serve-restart-button`` capability.

A Restart button in the Tweaks panel, a ``/restart`` endpoint that
re-execs the server in place, and the client-side wait-then-reload
wiring that brings the page back once the fresh server is up.
"""

from __future__ import annotations

import threading
import urllib.request
from pathlib import Path

from i2e_core import console, serve
from i2e_core.console.prefs import parse_prefs_from_cookie
from i2e_core.console.shell import _tweaks_panel


def test_tweaks_panel_has_restart_button():
    """The Tweaks panel renders a Restart button in a Server section."""
    panel = _tweaks_panel(parse_prefs_from_cookie(None))

    assert '<div class="tweak-section">Server</div>' in panel
    assert 'id="restart-server"' in panel
    assert "Restart server" in panel
    assert 'data-restart-url="/restart"' in panel
    # type="button" so it never submits the layout-prefs form it sits in.
    assert 'type="button"' in panel


def test_restart_endpoint_triggers_reexec(tmp_path, monkeypatch):
    """POST /restart shuts the server down and reaches the re-exec step."""
    reexeced = threading.Event()
    monkeypatch.setattr(serve, "_reexec", lambda: reexeced.set())

    url = serve.start_server(tmp_path, port=0, open_browser=False)
    try:
        req = urllib.request.Request(
            url.rstrip("/") + "/restart", method="POST"
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            assert resp.status == 200

        assert reexeced.wait(timeout=5), "/restart never reached _reexec()"
    finally:
        serve.stop_server(tmp_path)


def test_restart_button_reloads_after_10s():
    """The button carries a 10s delay and console.js wires the reload."""
    # The 10-second delay is server-rendered into the button markup.
    panel = _tweaks_panel(parse_prefs_from_cookie(None))
    assert 'data-reload-delay="10000"' in panel

    # console.js wires the button to a delayed full-page reload.
    js = (
        Path(console.__file__).parent / "static" / "console.js"
    ).read_text(encoding="utf-8")
    assert "restart-server" in js
    assert "data-reload-delay" in js
    assert "setTimeout" in js
    assert "location.reload" in js
