import json
import threading
from http.client import HTTPConnection
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import pytest

from shortener.server import build_server
from shortener.store import FileStore


@pytest.fixture
def server(tmp_path):
    store = FileStore(tmp_path / "shortener.json")
    srv = build_server(store, port=0)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    host, port = srv.server_address[:2]
    yield f"http://{host}:{port}"
    srv.shutdown()
    srv.server_close()
    thread.join(timeout=2)


def _post(base: str, path: str, body: dict, timeout: float = 2.0):
    req = Request(
        base + path,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return urlopen(req, timeout=timeout)


def _raw_get(base: str, path: str):
    parsed = urlparse(base)
    conn = HTTPConnection(parsed.hostname, parsed.port, timeout=2.0)
    conn.request("GET", path)
    resp = conn.getresponse()
    return resp.status, dict(resp.getheaders())


def test_shorten_and_redirect(server):
    resp = _post(server, "/shorten", {"url": "https://example.com/demo"})
    assert resp.status == 201
    payload = json.loads(resp.read())
    code = payload["code"]
    assert len(code) == 7

    status, headers = _raw_get(server, f"/{code}")
    assert status == 302
    assert headers["Location"] == "https://example.com/demo"


def test_shorten_rejects_unsafe_url(server):
    with pytest.raises(HTTPError) as exc:
        _post(server, "/shorten", {"url": "javascript:alert(1)"})
    assert exc.value.code == 400


def test_unknown_code_returns_404(server):
    status, _ = _raw_get(server, "/nope000")
    assert status == 404


def test_root_returns_health(server):
    resp = urlopen(server + "/", timeout=2.0)
    body = json.loads(resp.read())
    assert body == {"status": "ok", "service": "url-shortener"}
