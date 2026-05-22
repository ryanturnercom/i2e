"""Localhost HTTP server with SSE updates on ``.i2e/`` changes (epic 08).

Bind 127.0.0.1 only — refuses any other host. Ephemeral port. Writes
``.i2e/.serve.url`` while up; removes it on shutdown. Optional companion
to ``i2e-report``; the static file always works without a server.

CLI: ``python -m i2e_core.serve start|stop``.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
import time
import urllib.request
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Empty, Queue
from urllib.parse import urlparse

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .config import load_config
from .console.app import handle as console_handle
from .intent_authoring import demote_intent, promote_intent, set_intent_status
from .io_utils import atomic_write
from .paths import i2e_dir, serve_url_path


# ---------- Internal helpers ----------


_DEBOUNCE_SECONDS = 0.2

# Auto-reload coalesces a burst of source writes (an editor save, or
# i2e-develop fanning out across files) into a single process restart.
_CODE_DEBOUNCE_SECONDS = 0.4


class _ChangeBroker:
    """Fan-out broker for ``.i2e/`` change notifications.

    Each subscriber gets its own ``Queue``; the broker debounces incoming
    events so a burst of writes only yields one notification per debounce
    window.
    """

    def __init__(self) -> None:
        self._subs: list[Queue[str]] = []
        self._lock = threading.Lock()
        self._last_emitted: float = 0.0
        self._pending: str | None = None
        self._timer: threading.Timer | None = None

    def subscribe(self) -> Queue[str]:
        q: Queue[str] = Queue()
        with self._lock:
            self._subs.append(q)
        return q

    def unsubscribe(self, q: Queue[str]) -> None:
        with self._lock:
            try:
                self._subs.remove(q)
            except ValueError:
                pass

    def notify(self, path: str) -> None:
        with self._lock:
            self._pending = path
            if self._timer is not None:
                return
            self._timer = threading.Timer(_DEBOUNCE_SECONDS, self._flush)
            self._timer.daemon = True
            self._timer.start()

    def _flush(self) -> None:
        with self._lock:
            path = self._pending or ""
            self._pending = None
            self._timer = None
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait(path)
            except Exception:
                pass

    def close(self) -> None:
        with self._lock:
            if self._timer is not None:
                try:
                    self._timer.cancel()
                except Exception:
                    pass
                self._timer = None
            for q in list(self._subs):
                try:
                    q.put_nowait("__shutdown__")
                except Exception:
                    pass
            self._subs.clear()


_SELF_WRITTEN_NAMES = frozenset(
    {
        ".serve.url",
        "report.html",
        "report.html.tmp",
        ".preflight_cache.json",
        ".watch_state.json",
    }
)


class _WatchdogHandler(FileSystemEventHandler):
    def __init__(self, broker: _ChangeBroker, root_dir: Path) -> None:
        self._broker = broker
        self._root = root_dir
        # Ignore the .serve.url file (we wrote it ourselves) so we don't loop.
        self._url_file = serve_url_path(root_dir.parent)

    def _emit(self, src_path: str) -> None:
        # Self-written files at the .i2e/ root must not feed back into the
        # broker — every GET / re-renders report.html, which would otherwise
        # trigger a change SSE event, which would trigger location.reload()
        # in the browser, which would trigger another GET /, ad infinitum.
        # Keep this check tight (file name only, no extra stat calls) so the
        # event handler stays cheap.
        try:
            p = Path(src_path)
            if p.name in _SELF_WRITTEN_NAMES:
                return
        except Exception:
            pass
        self._broker.notify(src_path)

    def on_modified(self, event) -> None:
        if not event.is_directory:
            self._emit(event.src_path)

    def on_created(self, event) -> None:
        if not event.is_directory:
            self._emit(event.src_path)

    def on_deleted(self, event) -> None:
        if not event.is_directory:
            self._emit(event.src_path)


def code_watch_dir() -> Path:
    """Directory auto-reload watches for ``.py`` changes — the i2e_core package.

    Resolved from this module's own location, so it is exactly the code the
    running server executes. For an editable install that is ``src/i2e_core/``
    (dogfooding i2e on itself); for a normal install it points into
    site-packages, which simply never changes.
    """
    return Path(__file__).resolve().parent


class _CodeReloadHandler(FileSystemEventHandler):
    """Re-execs the server when a ``.py`` file under the code tree changes.

    A burst of writes — an editor saving several files, or i2e-develop
    fanning out — is debounced into a single restart. Only ``.py`` source
    triggers a restart: bytecode is irrelevant and static assets are served
    ``no-store``, so a plain refresh already picks those up.
    """

    def __init__(
        self,
        server: ThreadingHTTPServer,
        *,
        debounce: float = _CODE_DEBOUNCE_SECONDS,
    ) -> None:
        self._server = server
        self._debounce = debounce
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    def _on_change(self, event) -> None:
        if event.is_directory or not str(event.src_path).endswith(".py"):
            return
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce, self._fire)
            self._timer.daemon = True
            self._timer.start()

    def on_modified(self, event) -> None:
        self._on_change(event)

    def on_created(self, event) -> None:
        self._on_change(event)

    def on_deleted(self, event) -> None:
        self._on_change(event)

    def _fire(self) -> None:
        with self._lock:
            self._timer = None
        _restart(self._server)


def _make_handler_class(
    root: Path, broker: _ChangeBroker, shutdown_event: threading.Event
):
    """Build a request-handler class bound to this server instance's state."""

    class _Handler(BaseHTTPRequestHandler):
        # Silence the noisy default access log; we don't ship it anywhere
        # useful and it confuses test output.
        def log_message(self, format, *args):  # noqa: A002
            return

        def _write_text(self, status: int, body: str, content_type: str) -> None:
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802 — stdlib name
            parsed = urlparse(self.path)
            if parsed.path == "/events":
                self._serve_events()
                return
            self._delegate("GET", parsed.path, parsed.query, "")

        def do_POST(self) -> None:  # noqa: N802 — stdlib name
            parsed = urlparse(self.path)
            if parsed.path == "/shutdown":
                self._write_text(HTTPStatus.OK, "shutting down", "text/plain")
                # Shutdown must NOT happen on the handler thread, or the
                # server deadlocks on its own join. Schedule it.
                shutdown_event.set()
                threading.Thread(
                    target=self.server.shutdown, daemon=True
                ).start()
                return
            if parsed.path == "/restart":
                self._write_text(HTTPStatus.OK, "restarting", "text/plain")
                # Re-exec must run off the handler thread so this response
                # flushes first; _restart shuts down cleanly, then execs.
                shutdown_event.set()
                threading.Thread(
                    target=_restart, args=(self.server,), daemon=True
                ).start()
                return
            if parsed.path == "/intent/status":
                # Legacy JSON endpoint backing the static report.html
                # status controls (capability: intent-status-controls).
                self._serve_intent_status()
                return
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(length).decode("utf-8") if length else ""
            self._delegate("POST", parsed.path, parsed.query, body)

        def _delegate(self, method: str, path: str, query: str, body: str) -> None:
            """Hand a request to the console route table and write the response."""
            cookie = self.headers.get("Cookie")
            try:
                resp = console_handle(root, method, path, query, body, cookie)
            except Exception as exc:  # never crash the serve thread
                self._write_text(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    f"console error: {exc}",
                    "text/plain",
                )
                return
            data = resp.body
            self.send_response(resp.status)
            self.send_header("Content-Type", resp.content_type)
            self.send_header("Content-Length", str(len(data)))
            for key, value in resp.headers.items():
                self.send_header(key, value)
            if "Cache-Control" not in resp.headers:
                self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _serve_intent_status(self) -> None:
            try:
                length = int(self.headers.get("Content-Length") or "0")
                body = self.rfile.read(length).decode("utf-8") if length else ""
                payload = json.loads(body) if body else {}
            except Exception as e:
                self._write_text(
                    HTTPStatus.BAD_REQUEST,
                    json.dumps({"error": f"invalid json: {e}"}),
                    "application/json",
                )
                return
            slug = payload.get("slug")
            action = payload.get("action")
            if not isinstance(slug, str) or not slug:
                self._write_text(
                    HTTPStatus.BAD_REQUEST,
                    json.dumps({"error": "missing slug"}),
                    "application/json",
                )
                return
            try:
                if action == "promote":
                    old, new = promote_intent(root, slug)
                elif action == "demote":
                    old, new = demote_intent(root, slug)
                elif action == "set":
                    target = payload.get("status")
                    if not isinstance(target, str):
                        raise ValueError("missing 'status' for set action")
                    set_intent_status(root, slug, target)  # type: ignore[arg-type]
                    old, new = "?", target
                else:
                    raise ValueError(
                        f"unknown action {action!r} (use promote|demote|set)"
                    )
            except (FileNotFoundError, ValueError) as e:
                self._write_text(
                    HTTPStatus.BAD_REQUEST,
                    json.dumps({"error": str(e)}),
                    "application/json",
                )
                return
            self._write_text(
                HTTPStatus.OK,
                json.dumps({"slug": slug, "old": old, "new": new}),
                "application/json",
            )

        def _serve_events(self) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            q = broker.subscribe()
            try:
                # Initial nudge so the client knows we're listening.
                self._send_sse("ready", "")
                while not shutdown_event.is_set():
                    try:
                        payload = q.get(timeout=1.0)
                    except Empty:
                        try:
                            # Keep-alive comment line — clients ignore it.
                            self.wfile.write(b": keep-alive\n\n")
                            self.wfile.flush()
                        except Exception:
                            break
                        continue
                    if payload == "__shutdown__":
                        break
                    try:
                        self._send_sse("change", payload)
                    except Exception:
                        break
            finally:
                broker.unsubscribe(q)

        def _send_sse(self, event: str, data: str) -> None:
            body = f"event: {event}\ndata: {data}\n\n".encode("utf-8")
            self.wfile.write(body)
            self.wfile.flush()

    return _Handler


class _ServerHandle:
    """Bookkeeping for an in-process server thread + watcher."""

    def __init__(
        self,
        server: ThreadingHTTPServer,
        thread: threading.Thread,
        observer: Observer,
        broker: _ChangeBroker,
        url: str,
        url_file: Path,
        code_watch_dir: Path | None = None,
    ) -> None:
        self.server = server
        self.thread = thread
        self.observer = observer
        self.broker = broker
        self.url = url
        self.url_file = url_file
        # The i2e_core code dir watched for auto-reload, or None when
        # serve.autoreload is off. Surfaced for tests.
        self.code_watch_dir = code_watch_dir


# Registry of in-process handles, keyed by absolute root. Useful for tests
# that start/stop the server in the same process without going through HTTP.
_HANDLES: dict[str, _ServerHandle] = {}
_HANDLES_LOCK = threading.Lock()


# ---------- Public API ----------


def start_server(
    root: Path,
    host: str = "127.0.0.1",
    *,
    port: int | None = None,
    open_browser: bool | None = None,
    autoreload: bool | None = None,
) -> str:
    """Start the localhost server. Returns the URL.

    Refuses any host other than ``127.0.0.1`` (raises :class:`ValueError`).
    Writes ``.i2e/.serve.url`` while the server is up.

    ``port``, ``open_browser`` and ``autoreload`` fall back to
    ``.i2e/config.yaml`` when ``None``. Pass ``port=0`` for an ephemeral
    OS-assigned port (tests).
    """
    if host != "127.0.0.1":
        raise ValueError(
            f"i2e-serve binds 127.0.0.1 only; refusing host={host!r}"
        )
    root = Path(root).resolve()
    ldir = i2e_dir(root)
    ldir.mkdir(parents=True, exist_ok=True)

    if port is None or open_browser is None or autoreload is None:
        cfg = load_config(root)
        if port is None:
            port = cfg.serve.port
        if open_browser is None:
            open_browser = cfg.serve.open_browser
        if autoreload is None:
            autoreload = cfg.serve.autoreload

    broker = _ChangeBroker()
    shutdown_event = threading.Event()
    handler_cls = _make_handler_class(root, broker, shutdown_event)

    server = ThreadingHTTPServer((host, port), handler_cls)
    bound_port = server.server_address[1]
    url = f"http://{host}:{bound_port}/"

    url_file = serve_url_path(root)
    atomic_write(url_file, url)

    # Spawn watchdog observer for .i2e/.
    observer = Observer()
    watch_dir = ldir
    handler = _WatchdogHandler(broker, watch_dir)
    observer.schedule(handler, str(watch_dir), recursive=True)

    # When serve.autoreload is on, also watch the i2e_core package: a .py
    # change there re-execs the server in place so the operator never has
    # to restart by hand.
    code_dir: Path | None = None
    if autoreload:
        code_dir = code_watch_dir()
        observer.schedule(
            _CodeReloadHandler(server), str(code_dir), recursive=True
        )

    observer.start()

    def _serve() -> None:
        try:
            server.serve_forever(poll_interval=0.2)
        finally:
            try:
                observer.stop()
            except Exception:
                pass
            try:
                broker.close()
            except Exception:
                pass

    thread = threading.Thread(target=_serve, name="i2e-serve", daemon=True)
    thread.start()

    handle = _ServerHandle(
        server, thread, observer, broker, url, url_file, code_dir
    )
    with _HANDLES_LOCK:
        _HANDLES[str(root)] = handle

    if open_browser:
        _open_browser_async(url)

    return url


def _open_browser_async(url: str) -> None:
    """Fire ``webbrowser.open`` from a background thread after a brief delay.

    The delay gives the serve thread time to accept connections, so the
    first GET from the browser doesn't race the bind. Failures are
    swallowed — we never want a missing browser to crash the server.
    """

    def _go() -> None:
        try:
            time.sleep(0.15)
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=_go, name="i2e-serve-browser", daemon=True).start()


def _stop_in_process(root: Path) -> bool:
    with _HANDLES_LOCK:
        handle = _HANDLES.pop(str(Path(root).resolve()), None)
    if handle is None:
        return False
    try:
        handle.server.shutdown()
    except Exception:
        pass
    try:
        handle.observer.stop()
        handle.observer.join(timeout=2.0)
    except Exception:
        pass
    try:
        handle.broker.close()
    except Exception:
        pass
    try:
        handle.thread.join(timeout=2.0)
    except Exception:
        pass
    try:
        handle.server.server_close()
    except Exception:
        pass
    try:
        if handle.url_file.exists():
            handle.url_file.unlink()
    except Exception:
        pass
    return True


def stop_server(root: Path) -> None:
    """Stop the running server (if any) and clean up ``.serve.url``."""
    root = Path(root).resolve()

    # If we have an in-process handle (common in tests), shut it down directly.
    if _stop_in_process(root):
        return

    url_file = serve_url_path(root)
    if not url_file.exists():
        return
    try:
        url = url_file.read_text(encoding="utf-8").strip()
    except Exception:
        url = ""
    if url:
        try:
            req = urllib.request.Request(
                url.rstrip("/") + "/shutdown", method="POST"
            )
            with urllib.request.urlopen(req, timeout=2.0):
                pass
        except Exception:
            # Best-effort: still remove the file even if the server is gone.
            pass
    # Give the server a moment to actually exit before deleting the file.
    time.sleep(0.05)
    try:
        url_file.unlink()
    except FileNotFoundError:
        pass


# ---------- Restart ----------


def _reexec() -> None:  # pragma: no cover - replaces the process image
    """Replace the current process with a fresh ``i2e-serve`` invocation.

    ``os.execv`` keeps the same PID and controlling terminal, so the
    operator's foreground ``start.sh`` process restarts in place and
    picks up code or config changes.
    """
    os.execv(
        sys.executable,
        [sys.executable, "-m", "i2e_core.serve", *sys.argv[1:]],
    )


def _restart(server: ThreadingHTTPServer) -> None:
    """Shut the server down cleanly, then re-exec the process.

    Split from :func:`_reexec` so tests can patch the exec step and
    assert the ``/restart`` endpoint reaches it without replacing the
    test process.
    """
    try:
        server.shutdown()
    except Exception:
        pass
    _reexec()


# ---------- CLI ----------


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m i2e_core.serve",
        description="Start or stop the localhost i2e-serve server.",
    )
    parser.add_argument("command", choices=("start", "stop"))
    parser.add_argument(
        "--root",
        default=".",
        help="Project root (containing .i2e/). Defaults to cwd.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Bind to this port (default: serve.port from .i2e/config.yaml).",
    )
    browser_group = parser.add_mutually_exclusive_group()
    browser_group.add_argument(
        "--open-browser",
        dest="open_browser",
        action="store_true",
        default=None,
        help="Open the served URL in the default browser (overrides config).",
    )
    browser_group.add_argument(
        "--no-browser",
        dest="open_browser",
        action="store_false",
        help="Do not open the browser (overrides config).",
    )
    reload_group = parser.add_mutually_exclusive_group()
    reload_group.add_argument(
        "--autoreload",
        dest="autoreload",
        action="store_true",
        default=None,
        help="Re-exec the server when i2e_core code changes (overrides config).",
    )
    reload_group.add_argument(
        "--no-autoreload",
        dest="autoreload",
        action="store_false",
        help="Do not auto-reload on code changes (overrides config).",
    )
    args = parser.parse_args(argv)

    root = Path(args.root)
    if args.command == "start":
        url = start_server(
            root,
            host=args.host,
            port=args.port,
            open_browser=args.open_browser,
            autoreload=args.autoreload,
        )
        print(json.dumps({"url": url}), flush=True)
        # The serve thread is a daemon — if we return here, the process exits
        # and the server dies with it. Block on the thread's join() so the CLI
        # stays alive until /shutdown POST or SIGINT. Then clean up regardless
        # of which path ended us.
        handle = _HANDLES.get(str(root.resolve()))

        def _on_sigint(_signum, _frame):
            if handle is not None:
                try:
                    handle.server.shutdown()
                except Exception:
                    pass

        try:
            signal.signal(signal.SIGINT, _on_sigint)
        except (ValueError, OSError):
            # Not in the main thread, or platform refuses — fall back to
            # default behaviour (KeyboardInterrupt unwinds the join).
            pass

        if handle is not None:
            try:
                handle.thread.join()
            except KeyboardInterrupt:
                try:
                    handle.server.shutdown()
                    handle.thread.join(timeout=5)
                except Exception:
                    pass

        stop_server(root)
        return 0
    if args.command == "stop":
        stop_server(root)
        print(json.dumps({"stopped": True}))
        return 0
    return 1


if __name__ == "__main__":  # pragma: no cover - thin CLI shim
    raise SystemExit(_main(sys.argv[1:]))


__all__ = ["code_watch_dir", "start_server", "stop_server"]
