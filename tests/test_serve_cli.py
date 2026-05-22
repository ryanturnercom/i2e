"""CLI start blocks until shutdown — proves the daemon-thread fix.

`python -m i2e_core.serve start` must keep the parent process alive while
the HTTP server runs, so backgrounding the CLI yields a URL that is still
reachable after the launching call returns. These tests spawn the real CLI
as a subprocess so the daemon-thread regression cannot hide behind in-process
shortcuts.
"""

from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from i2e_core.paths import serve_url_path


def _make_project(root: Path) -> None:
    for sub in ("context", "intents", "evidence", "pending", "logs"):
        (root / ".i2e" / sub).mkdir(parents=True, exist_ok=True)


def _wait_for_url(url_file: Path, timeout: float = 10.0) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if url_file.exists():
            text = url_file.read_text(encoding="utf-8").strip()
            if text:
                return text
        time.sleep(0.05)
    raise TimeoutError(f"{url_file} did not appear within {timeout}s")


def _start_cli(root: Path) -> subprocess.Popen:
    # --port 0 → ephemeral OS-assigned port so concurrent / back-to-back
    # test runs never fight for the static 4230. --no-browser keeps the
    # suite from popping browser tabs. (CLAUDE.md: tests stay ephemeral.)
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "i2e_core.serve",
            "start",
            "--root",
            str(root),
            "--port",
            "0",
            "--no-browser",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _run_stop_cli(root: Path) -> None:
    subprocess.run(
        [sys.executable, "-m", "i2e_core.serve", "stop", "--root", str(root)],
        check=True,
        timeout=10,
        capture_output=True,
    )


def _terminate(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def test_start_keeps_serving_after_launch_returns(tmp_path: Path) -> None:
    _make_project(tmp_path)
    url_file = serve_url_path(tmp_path)
    proc = _start_cli(tmp_path)
    try:
        url = _wait_for_url(url_file)
        # The daemon-thread bug would have killed the process by now. If
        # poll() returns non-None, start did not block.
        assert proc.poll() is None, (
            "CLI exited before /shutdown — start subcommand is not blocking"
        )
        with urllib.request.urlopen(url, timeout=5) as resp:
            assert resp.status == 200
    finally:
        try:
            _run_stop_cli(tmp_path)
            proc.wait(timeout=10)
        finally:
            _terminate(proc)


def test_stop_terminates_blocking_start(tmp_path: Path) -> None:
    _make_project(tmp_path)
    url_file = serve_url_path(tmp_path)
    proc = _start_cli(tmp_path)
    try:
        _wait_for_url(url_file)
        assert proc.poll() is None
        _run_stop_cli(tmp_path)
        exit_code = proc.wait(timeout=10)
        assert exit_code == 0
    finally:
        _terminate(proc)


def test_no_stale_serve_url_after_clean_shutdown(tmp_path: Path) -> None:
    _make_project(tmp_path)
    url_file = serve_url_path(tmp_path)
    proc = _start_cli(tmp_path)
    try:
        _wait_for_url(url_file)
        _run_stop_cli(tmp_path)
        proc.wait(timeout=10)
    finally:
        _terminate(proc)
    assert not url_file.exists(), (
        ".serve.url should be removed after a clean shutdown"
    )
