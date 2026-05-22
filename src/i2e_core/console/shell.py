"""Console page chrome — wraps a view body in sidebar + topbar + footer.

Layout preferences ride in the ``i2e_console_prefs`` cookie; :func:`page`
parses it, applies the density class, picks the sidebar mode, and renders
the floating Tweaks panel that writes the cookie back.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from . import ui
from .prefs import parse_prefs_from_cookie
from .state import ConsoleState, gather
from .views.sidebar import render_sidebar

_FONTS = (
    "https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700"
    "&family=JetBrains+Mono:wght@400;500;600&family=Rock+Salt&display=swap"
)

# Tweak axes — (cookie key, label, [(value, display), ...]).
_TWEAK_AXES = (
    ("theme", "Theme", (("light", "Light"), ("dark", "Dark"))),
    ("density", "Density", (("relaxed", "Relaxed"), ("dense", "Dense"))),
    (
        "sidebar",
        "Sidebar",
        (("grouped", "Grouped"), ("flat", "Flat"), ("tree", "Tree by spec")),
    ),
    (
        "dashboard",
        "Dashboard",
        (("cockpit", "Cockpit"), ("arc", "IDEA arc"), ("inbox", "Inbox")),
    ),
    ("intent", "Intent detail", (("split", "Split"), ("single", "Single"))),
    ("logs", "Logs default", (("timeline", "Timeline"), ("table", "Table"))),
)


def _topbar(state: ConsoleState, eyebrow: str, title: str) -> str:
    workers = len(state.workers)
    pendings = len(state.pendings)
    clock = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M") + "Z"
    pulses = []
    if workers:
        pulses.append(
            f'<div class="tb-pulse">{ui.pulse()}'
            f"<span>{workers} running</span></div>"
        )
    if pendings:
        pulses.append(
            '<div class="tb-pulse">'
            '<span class="dot7" style="background:var(--lilac-dot)"></span>'
            f"<span>{pendings} need attention</span></div>"
        )
    return f"""<div class="topbar">
  <div class="tb-context">
    {ui.eyebrow(eyebrow)}
    <span class="mono faded">·</span>
    <span class="tb-title">{ui.esc(title)}</span>
  </div>
  <div class="tb-meta">{"".join(pulses)}<span class="tb-clock">{ui.esc(clock)}</span></div>
</div>"""


def _tweaks_panel(prefs: dict[str, str]) -> str:
    rows = ['<div class="tweak-section">Layout</div>']
    for key, label, opts in _TWEAK_AXES:
        current = prefs.get(key, "")
        options = "".join(
            f'<option value="{ui.esc(value)}"'
            f'{" selected" if value == current else ""}>{ui.esc(display)}</option>'
            for value, display in opts
        )
        rows.append(
            f'<label class="tweak-row"><span>{ui.esc(label)}</span>'
            f'<select name="{key}">{options}</select></label>'
        )
    return (
        '<details class="tweaks-panel" id="tweaks-panel">'
        '<summary title="Layout tweaks">&#9881;</summary>'
        '<form hx-post="/api/prefs" hx-trigger="change">'
        + "".join(rows)
        + '<div class="tweak-hint">saved to the i2e_console_prefs cookie</div>'
        "</form></details>"
    )


def page(
    *,
    root: Path,
    active: str,
    body: str,
    state: ConsoleState | None = None,
    eyebrow: str = "",
    title: str = "",
    selected_slug: str | None = None,
    path: str = "/",
    sidebar_filter: str | None = None,
    sidebar_q: str | None = None,
    cookie: str | None = None,
) -> str:
    """Render a full console page: ``<!doctype html>`` … chrome … ``body``."""
    if state is None:
        state = gather(Path(root))
    prefs = parse_prefs_from_cookie(cookie)
    sidebar = render_sidebar(
        root,
        mode=prefs["sidebar"],
        active=active,
        selected_slug=selected_slug,
        state=state,
        flt=sidebar_filter,
        q=sidebar_q,
    )
    topbar = _topbar(state, eyebrow or active.title(), title)
    head_title = title or eyebrow or "console"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>i2e console — {ui.esc(head_title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{_FONTS}">
<link rel="stylesheet" href="/static/console.css">
<script src="/static/htmx.min.js" defer></script>
<script src="/static/console.js" defer></script>
</head>
<body class="console density-{ui.esc(prefs['density'])} theme-{ui.esc(prefs['theme'])}">
<div class="app">
{sidebar}
<main class="main">
{topbar}
<div class="content">
{body}
</div>
<footer class="footer">
<span class="mono">i2e console · 127.0.0.1 · loopback only</span> —
<a href="https://ryanturner.com">ryanturner.com</a>
</footer>
</main>
</div>
<div class="toast-wrap" id="toasts"></div>
<div id="modal-mount"></div>
{_tweaks_panel(prefs)}
</body>
</html>"""
