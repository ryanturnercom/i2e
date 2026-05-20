"""Localhost HTTP server with SSE updates on ``.i2e/`` changes (epic 08).

Bind 127.0.0.1 only — refuses any other host. Ephemeral port. Writes
``.i2e/.serve.url`` while up; removes it on shutdown. Optional companion
to ``i2e-report``; the static file always works without a server.

CLI: ``python -m i2e_core.serve start|stop``.
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
import time
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Empty, Queue
from urllib.parse import urlparse

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .io_utils import atomic_write
from .paths import i2e_dir, serve_url_path
from .report import render


# ---------- Internal helpers ----------


_DEBOUNCE_SECONDS = 0.2


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


class _WatchdogHandler(FileSystemEventHandler):
    def __init__(self, broker: _ChangeBroker, root_dir: Path) -> None:
        self._broker = broker
        self._root = root_dir
        # Ignore the .serve.url file (we wrote it ourselves) so we don't loop.
        self._url_file = serve_url_path(root_dir.parent)

    def _emit(self, src_path: str) -> None:
        try:
            p = Path(src_path)
            if p.name == self._url_file.name:
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
            path = urlparse(self.path).path
            if path == "/" or path == "/index.html":
                self._serve_index()
            elif path == "/events":
                self._serve_events()
            else:
                self._write_text(HTTPStatus.NOT_FOUND, "not found", "text/plain")

        def do_POST(self) -> None:  # noqa: N802 — stdlib name
            path = urlparse(self.path).path
            if path == "/shutdown":
                self._write_text(HTTPStatus.OK, "shutting down", "text/plain")
                # Shutdown must NOT happen on the handler thread, or the
                # server deadlocks on its own join. Schedule it.
                shutdown_event.set()
                threading.Thread(
                    target=self.server.shutdown, daemon=True
                ).start()
            else:
                self._write_text(HTTPStatus.NOT_FOUND, "not found", "text/plain")

        def _serve_index(self) -> None:
            try:
                report_file = render(root)
                html = Path(report_file).read_text(encoding="utf-8")
            except Exception as e:
                self._write_text(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    f"render failed: {e}",
                    "text/plain",
                )
                return
            self._write_text(HTTPStatus.OK, html, "text/html; charset=utf-8")

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
    ) -> None:
        self.server = server
        self.thread = thread
        self.observer = observer
        self.broker = broker
        self.url = url
        self.url_file = url_file


# Registry of in-process handles, keyed by absolute root. Useful for tests
# that start/stop the server in the same process without going through HTTP.
_HANDLES: dict[str, _ServerHandle] = {}
_HANDLES_LOCK = threading.Lock()


# ---------- Public API ----------


def start_server(root: Path, host: str = "127.0.0.1") -> str:
    """Start the localhost server. Returns the URL.

    Refuses any host other than ``127.0.0.1`` (raises :class:`ValueError`).
    Writes ``.i2e/.serve.url`` while the server is up.
    """
    if host != "127.0.0.1":
        raise ValueError(
            f"i2e-serve binds 127.0.0.1 only; refusing host={host!r}"
        )
    root = Path(root).resolve()
    ldir = i2e_dir(root)
    ldir.mkdir(parents=True, exist_ok=True)

    broker = _ChangeBroker()
    shutdown_event = threading.Event()
    handler_cls = _make_handler_class(root, broker, shutdown_event)

    server = ThreadingHTTPServer((host, 0), handler_cls)
    port = server.server_address[1]
    url = f"http://{host}:{port}/"

    url_file = serve_url_path(root)
    atomic_write(url_file, url)

    # Spawn watchdog observer for .i2e/.
    observer = Observer()
    watch_dir = ldir
    handler = _WatchdogHandler(broker, watch_dir)
    observer.schedule(handler, str(watch_dir), recursive=True)
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

    handle = _ServerHandle(server, thread, observer, broker, url, url_file)
    with _HANDLES_LOCK:
        _HANDLES[str(root)] = handle
    return url


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
    args = parser.parse_args(argv)

    root = Path(args.root)
    if args.command == "start":
        url = start_server(root, host=args.host)
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


__all__ = ["start_server", "stop_server"]
