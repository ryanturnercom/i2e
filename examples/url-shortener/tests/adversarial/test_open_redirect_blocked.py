import pytest

from shortener.service import is_safe_url, shorten
from shortener.store import FileStore


@pytest.fixture
def store(tmp_path):
    return FileStore(tmp_path / "shortener.json")


HOSTILE_URLS = [
    "javascript:alert(1)",
    "JavaScript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "file:///etc/passwd",
    "file://C:/Windows/System32",
    "ftp://example.com/",
    "vbscript:msgbox(1)",
    "//example.com/no-scheme",
    "  ",
    "",
    "not-a-url",
    "http://",
    "https://",
]


@pytest.mark.parametrize("bad", HOSTILE_URLS)
def test_is_safe_url_rejects(bad):
    assert is_safe_url(bad) is False


@pytest.mark.parametrize("bad", HOSTILE_URLS)
def test_shorten_refuses(store, bad):
    with pytest.raises(ValueError):
        shorten(store, bad)


@pytest.mark.parametrize(
    "good",
    [
        "http://example.com",
        "https://example.com/",
        "https://example.com/path?query=1#frag",
        "http://127.0.0.1:8000/x",
    ],
)
def test_safe_urls_pass(good):
    assert is_safe_url(good) is True
