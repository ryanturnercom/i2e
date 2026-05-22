"""Last-tick summary renderer — the new, deterministic ``report.html``.

After the console epics land, ``report.html`` shrinks from a full state
snapshot to a single-page summary of the most recent tick. The rich UI
lives in the console; this artifact stays useful for CI, release notes,
and snapshotting without a server.

Same rules as the legacy report:

- Deterministic output (no wall-clock; reads ``ran_at`` from the latest
  tick log).
- Self-contained HTML (inline CSS) so the file works without serve.
- Zero LLM tokens — pure Python.

Empty-state fallback: when ``.i2e/logs/`` has no tick logs the page
says "No ticks yet — run /i2e."
"""

from __future__ import annotations

from html import escape
from pathlib import Path

from ..paths import logs_dir, report_path
from ..tick_log import _read_tick


_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>i2e last tick</title>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 720px; margin: 2rem auto; padding: 0 1rem; color: #1d1d1f; }}
  h1 {{ margin-bottom: 0.25rem; }}
  .meta {{ color: #6e6e73; font-size: 0.9rem; margin-bottom: 1.5rem; }}
  h2 {{ font-size: 1rem; margin-top: 1.5rem; }}
  ul {{ padding-left: 1.25rem; }}
  li {{ margin: 0.25rem 0; }}
  .empty {{ color: #6e6e73; font-style: italic; }}
</style>
</head>
<body>
{body}
</body>
</html>
"""

_EMPTY_BODY = """<h1>i2e</h1>
<p class="empty">No ticks yet — run /i2e.</p>"""


def _latest_tick(root: Path):
    base = logs_dir(Path(root))
    if not base.exists():
        return None
    cands = sorted(
        (p for p in base.glob("*-tick.yaml") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for p in cands:
        tl = _read_tick(p)
        if tl is not None:
            return tl
    return None


def _render_body(tick) -> str:
    lines = [
        f"<h1>Last tick · {escape(tick.tick_id)}</h1>",
        f'<div class="meta">{escape(tick.ran_at.strftime("%Y-%m-%d %H:%MZ"))}</div>',
        f"<h2>Actions ({len(tick.actions)})</h2>",
        "<ul>",
    ]
    for action in tick.actions:
        lines.append(f"<li>{escape(action)}</li>")
    lines.append("</ul>")
    return "\n".join(lines)


def render_last_tick(root: Path) -> str:
    """Return the HTML for the last-tick summary page."""
    tick = _latest_tick(Path(root))
    body = _EMPTY_BODY if tick is None else _render_body(tick)
    return _TEMPLATE.format(body=body)


def render(root: Path) -> Path:
    """Write ``report.html`` containing the last-tick summary; return the path."""
    from ..io_utils import atomic_write

    out = report_path(Path(root))
    out.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(out, render_last_tick(root))
    return out
