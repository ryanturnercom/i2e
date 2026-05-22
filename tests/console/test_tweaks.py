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
from i2e_core.console.shell import _tweaks_panel, page


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
    assert prefs["intent"] == DEFAULT_PREFS["intent"]
    assert prefs["logs"] == DEFAULT_PREFS["logs"]


def _bootstrap(root):
    """Minimal .i2e/ tree so shell.page() can render against a tmp root."""
    for sub in ("intents", "evidence", "logs", "pending"):
        (root / ".i2e" / sub).mkdir(parents=True)


def test_theme_axis_present_and_persists(tmp_path):
    """Light/Dark mode shows up in the Tweaks panel and is remembered.

    Covers the ``light-and-dark-mode`` capability: the theme axis must be
    visible in the tweak settings, the choice must round-trip through the
    ``i2e_console_prefs`` cookie, and the remembered value must be applied
    to the page ``<body>`` on every render (so a refresh keeps the theme).
    """
    # Theme is a first-class pref with a light default.
    assert DEFAULT_PREFS["theme"] == "light"

    # The Tweaks panel offers a Light/Dark theme control.
    panel = _tweaks_panel(parse_prefs_from_cookie(None))
    assert 'name="theme"' in panel
    assert ">Light<" in panel
    assert ">Dark<" in panel

    # A chosen theme round-trips through the cookie — remembered on refresh.
    header = build_set_cookie_header({**DEFAULT_PREFS, "theme": "dark"})
    cookie = header.split(";", 1)[0]
    assert parse_prefs_from_cookie(cookie)["theme"] == "dark"

    # The panel reflects the remembered choice as the selected option.
    assert '<option value="dark" selected>' in _tweaks_panel(
        parse_prefs_from_cookie(cookie)
    )

    # The remembered theme is applied to the page <body> on every render.
    _bootstrap(tmp_path)
    assert "theme-light" in page(root=tmp_path, active="dashboard", body="x")
    assert "theme-dark" in page(
        root=tmp_path, active="dashboard", body="x", cookie=cookie
    )


def test_theme_axis_in_panel(tmp_path):
    """A full page render mounts the Tweaks panel with the Theme axis.

    The ``theme-axis-in-panel`` evidence item: the Light/Dark Theme
    select is added to the panel alongside the existing layout axes,
    not in place of them.
    """
    _bootstrap(tmp_path)
    html = page(root=tmp_path, active="dashboard", body="x")

    # The Tweaks panel is mounted in the rendered page.
    assert 'class="tweaks-panel"' in html

    # A labelled Light/Dark Theme select.
    assert "<span>Theme</span>" in html
    assert 'select name="theme"' in html
    assert '<option value="light"' in html
    assert '<option value="dark"' in html

    # Added, not swapped in — the existing layout axes are still there.
    for label in ("Density", "Sidebar", "Intent detail"):
        assert f"<span>{label}</span>" in html
