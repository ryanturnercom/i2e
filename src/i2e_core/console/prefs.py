"""Cookie-based preferences for the console (Tweaks panel).

The ``i2e_console_prefs`` cookie carries the user's chosen layout
variants so the server can render the right markup on every request.
HTMX is server-driven; cookies travel with every request.

Schema:

    {
      "density":   "dense" | "relaxed",
      "sidebar":   "grouped" | "flat" | "tree",
      "dashboard": "cockpit" | "arc" | "inbox",
      "intent":    "single" | "split",
      "logs":      "timeline" | "table",
    }

Unknown keys are silently dropped; missing keys fall back to the
default value. The cookie is set ``Path=/; SameSite=Strict;
Max-Age=31536000`` (one year).
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote, unquote

COOKIE_NAME = "i2e_console_prefs"

DEFAULT_PREFS: dict[str, str] = {
    "density": "relaxed",
    "sidebar": "grouped",
    "dashboard": "cockpit",
    "intent": "split",
    "logs": "timeline",
}


def parse_prefs_from_cookie(cookie_header: str | None) -> dict[str, str]:
    """Extract and validate the prefs dict from a ``Cookie:`` header value."""
    out = dict(DEFAULT_PREFS)
    if not cookie_header:
        return out
    for part in cookie_header.split(";"):
        name, _, value = part.strip().partition("=")
        if name != COOKIE_NAME or not value:
            continue
        try:
            parsed: Any = json.loads(unquote(value))
        except (ValueError, json.JSONDecodeError):
            return out
        if not isinstance(parsed, dict):
            return out
        for k, v in parsed.items():
            if k in DEFAULT_PREFS and isinstance(v, str):
                out[k] = v
        return out
    return out


def build_set_cookie_header(prefs: dict[str, str]) -> str:
    """Render a ``Set-Cookie`` header value from a prefs dict."""
    filtered = {k: v for k, v in prefs.items() if k in DEFAULT_PREFS}
    body = quote(json.dumps(filtered, separators=(",", ":")))
    return f"{COOKIE_NAME}={body}; Path=/; SameSite=Strict; Max-Age=31536000"
