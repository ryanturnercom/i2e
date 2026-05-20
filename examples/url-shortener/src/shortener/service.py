from __future__ import annotations

import secrets
from urllib.parse import urlparse

from .store import FileStore

CODE_LENGTH = 7
ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
ALLOWED_SCHEMES = frozenset({"http", "https"})


def generate_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def is_safe_url(url: str) -> bool:
    if not isinstance(url, str) or not url.strip():
        return False
    parsed = urlparse(url)
    return parsed.scheme in ALLOWED_SCHEMES and bool(parsed.netloc)


def shorten(store: FileStore, url: str) -> str:
    if not is_safe_url(url):
        raise ValueError(f"unsafe or malformed url: {url!r}")
    for _ in range(10):
        code = generate_code()
        if store.get(code) is None:
            store.put(code, url)
            return code
    raise RuntimeError("could not generate a unique code after 10 attempts")


def resolve(store: FileStore, code: str) -> str | None:
    return store.get(code)
