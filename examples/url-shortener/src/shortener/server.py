from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .service import resolve, shorten
from .store import FileStore


def make_handler(store: FileStore) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            code = urlparse(self.path).path.lstrip("/")
            if not code:
                self._json(200, {"status": "ok", "service": "url-shortener"})
                return
            url = resolve(store, code)
            if url is None:
                self._json(404, {"error": "not found"})
                return
            self.send_response(302)
            self.send_header("Location", url)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/shorten":
                self._json(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8") if length else ""
            try:
                payload = json.loads(raw)
                url = payload["url"]
            except (json.JSONDecodeError, KeyError, TypeError):
                self._json(400, {"error": "expected JSON body with a 'url' field"})
                return
            try:
                code = shorten(store, url)
            except ValueError as e:
                self._json(400, {"error": str(e)})
                return
            host = self.headers.get("Host", "127.0.0.1")
            self._json(201, {"code": code, "short_url": f"http://{host}/{code}"})

        def log_message(self, *_args: object) -> None:
            return

        def _json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def build_server(store: FileStore, host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(store))


def _main() -> None:
    p = argparse.ArgumentParser(description="Run the URL shortener server.")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--data", type=Path, default=Path("data/shortener.json"))
    args = p.parse_args()
    store = FileStore(args.data)
    server = build_server(store, host=args.host, port=args.port)
    host, port = server.server_address[:2]
    print(f"Serving on http://{host}:{port}/  (data: {args.data})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    _main()
