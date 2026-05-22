"""Static-port + browser-open behaviour for ``i2e-serve``."""

from __future__ import annotations

import socket
import time
from pathlib import Path
from urllib.parse import urlparse

from i2e_core import serve as serve_mod
from i2e_core.serve import start_server, stop_server


def _free_port() -> int:
    """Reserve a free TCP port from the OS, then close so it can be reused."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _write_serve_config(project: Path, port: int, open_browser: bool) -> None:
    cfg_dir = project / ".i2e"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "config.yaml").write_text(
        f"serve:\n  port: {port}\n  open_browser: {str(open_browser).lower()}\n",
        encoding="utf-8",
    )


def test_static_port_from_config_is_used(project: Path) -> None:
    port = _free_port()
    _write_serve_config(project, port=port, open_browser=False)
    try:
        url = start_server(project)
        assert urlparse(url).port == port
    finally:
        stop_server(project)


def test_explicit_port_arg_overrides_config(project: Path) -> None:
    # Config says one port, kwarg says another — kwarg wins.
    cfg_port = _free_port()
    arg_port = _free_port()
    while arg_port == cfg_port:
        arg_port = _free_port()
    _write_serve_config(project, port=cfg_port, open_browser=False)
    try:
        url = start_server(project, port=arg_port, open_browser=False)
        assert urlparse(url).port == arg_port
    finally:
        stop_server(project)


def test_browser_opens_when_enabled(project: Path, monkeypatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr(
        serve_mod.webbrowser, "open", lambda u: opened.append(u) or True
    )
    try:
        url = start_server(project, port=0, open_browser=True)
        # The open() call fires from a background thread after a short delay.
        deadline = time.time() + 2.0
        while time.time() < deadline and not opened:
            time.sleep(0.05)
        assert opened == [url]
    finally:
        stop_server(project)


def test_browser_does_not_open_when_disabled(project: Path, monkeypatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr(
        serve_mod.webbrowser, "open", lambda u: opened.append(u) or True
    )
    try:
        start_server(project, port=0, open_browser=False)
        # Even after waiting past the launch delay, no browser call.
        time.sleep(0.35)
        assert opened == []
    finally:
        stop_server(project)
