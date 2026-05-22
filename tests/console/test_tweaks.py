"""Tweaks panel — cookie write + server-side prefs read."""

from __future__ import annotations

import json
from urllib.parse import quote

from i2e_core.console.prefs import (
    COOKIE_NAME,
    DEFAULT_PREFS,
    build_set_cookie_header,
    parse_prefs_from_cookie,
)


def test_writes_cookie_on_change():
    prefs = dict(DEFAULT_PREFS)
    prefs["density"] = "dense"

    header = build_set_cookie_header(prefs)

    assert header.startswith(f"{COOKIE_NAME}=")
    assert "Path=/" in header
    assert "SameSite=Strict" in header
    assert "Max-Age=" in header
    # The encoded body must round-trip back to the same dict.
    roundtrip = parse_prefs_from_cookie(header.split(";", 1)[0])
    assert roundtrip["density"] == "dense"


def test_server_renders_variant_from_cookie():
    encoded = quote(json.dumps({"density": "dense", "sidebar": "tree"}))
    cookie_header = f"{COOKIE_NAME}={encoded}"

    prefs = parse_prefs_from_cookie(cookie_header)

    # Set values come from the cookie.
    assert prefs["density"] == "dense"
    assert prefs["sidebar"] == "tree"
    # Unset values fall back to defaults.
    assert prefs["dashboard"] == DEFAULT_PREFS["dashboard"]
    assert prefs["intent"] == DEFAULT_PREFS["intent"]
    assert prefs["logs"] == DEFAULT_PREFS["logs"]
