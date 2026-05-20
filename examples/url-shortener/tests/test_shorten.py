import re

import pytest

from shortener.service import CODE_LENGTH, resolve, shorten
from shortener.store import FileStore


@pytest.fixture
def store(tmp_path):
    return FileStore(tmp_path / "shortener.json")


def test_returns_7_char_code(store):
    code = shorten(store, "https://example.com")
    assert len(code) == CODE_LENGTH == 7
    assert re.fullmatch(r"[A-Za-z0-9]{7}", code)


def test_round_trip(store):
    long_url = "https://example.com/articles/2026/url-shortening?ref=demo"
    code = shorten(store, long_url)
    assert resolve(store, code) == long_url


def test_unique_codes_under_load(store):
    codes = {shorten(store, f"https://example.com/p/{i}") for i in range(200)}
    assert len(codes) == 200


def test_resolve_unknown_code(store):
    assert resolve(store, "missing") is None


def test_persists_across_instances(tmp_path):
    path = tmp_path / "shortener.json"
    code = shorten(FileStore(path), "https://example.com/persisted")
    assert resolve(FileStore(path), code) == "https://example.com/persisted"
