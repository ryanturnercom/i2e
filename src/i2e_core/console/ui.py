"""Shared HTML component helpers for the console.

Server-rendered equivalents of the JSX primitives in
``.documentation/i2e-console/project/components.jsx`` — badges, dots,
mono chips, effort pips, phase pills, icons.
"""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape as _escape

_VERDICT_LABEL = {
    "pass": "pass",
    "met": "met",
    "fail": "fail",
    "unmet": "unmet",
    "trending": "trending",
    "awaiting_human": "awaiting human",
    "running": "running",
}


def esc(value: object) -> str:
    """HTML-escape any value (text + attribute safe)."""
    return _escape(str(value if value is not None else ""), quote=True)


def mono(text: object, *, faded: bool = False, cls: str = "") -> str:
    klass = "mono faded" if faded else "mono"
    if cls:
        klass = f"{klass} {cls}"
    return f'<span class="{klass}">{esc(text)}</span>'


def eyebrow(text: object) -> str:
    return f'<div class="eyebrow">{esc(text)}</div>'


def code_chip(text: object) -> str:
    return f'<span class="code-chip">{esc(text)}</span>'


def dot(kind: str) -> str:
    return f'<span class="dot {esc(kind)}"></span>'


def pulse(*, variant: str = "") -> str:
    klass = f"pulse {variant}".strip()
    return f'<span class="{klass}"></span>'


def badge(text: object, kind: str = "default", *, upper: bool = False) -> str:
    klass = f"badge {esc(kind)}"
    if upper:
        klass += " upper"
    return f'<span class="{klass}">{esc(text)}</span>'


def status_badge(status: str) -> str:
    return f'<span class="badge {esc(status)} upper">{esc(status)}</span>'


def verdict_badge(verdict: str | None) -> str:
    if not verdict:
        return '<span class="badge nodata">no data</span>'
    label = _VERDICT_LABEL.get(verdict, verdict)
    return (
        f'<span class="badge {esc(verdict)}">'
        f'<span class="bdot dot {esc(verdict)}"></span>{esc(label)}</span>'
    )


def type_badge(item_type: str) -> str:
    klass = "type-badge case" if item_type == "case" else "type-badge"
    return f'<span class="{klass}">{esc(item_type.upper())}</span>'


_EFFORT_MAX = {"lazy": 0, "low": 3, "medium": 6, "high": 10}


def effort_pip(effort: str, attempts_used: int = 0) -> str:
    max_n = _EFFORT_MAX.get(effort, 6)
    if max_n == 0:
        return '<span class="effort-lazy">LAZY</span>'
    pips = []
    for i in range(max_n):
        if i < attempts_used:
            cls = "pip over" if attempts_used >= max_n else "pip on"
        else:
            cls = "pip"
        pips.append(f'<span class="{cls}"></span>')
    return (
        f'<span class="effort-pip"><span class="pn">{attempts_used}/{max_n}</span>'
        + "".join(pips)
        + "</span>"
    )


_PHASE_LETTER = {"intent": "I", "develop": "D", "evidence": "E", "adapt": "A"}


def phase_pill(phase: str) -> str:
    letter = _PHASE_LETTER.get(phase, "I")
    klass = "phase-pill develop" if phase == "develop" else "phase-pill"
    return f'<span class="{klass}">{letter}</span>'


def empty_state(title: str, subtitle: str = "") -> str:
    sub = f'<div>{esc(subtitle)}</div>' if subtitle else ""
    return (
        f'<div class="empty-state"><div class="es-title">{esc(title)}</div>{sub}</div>'
    )


def relative_time(value: datetime | str | None) -> str:
    """A compact 'x ago' string. Tolerates naive datetimes and ISO strings."""
    if value is None:
        return "—"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - value
    secs = int(delta.total_seconds())
    if secs < 0:
        return "just now"
    if secs < 60:
        return "just now"
    mins = secs // 60
    if mins < 60:
        return f"{mins}m ago"
    hours = mins // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days < 30:
        return f"{days}d ago"
    return f"{days // 30}mo ago"


# ── inline SVG icons (nav rail) ──────────────────────────────────────────────

_ICONS = {
    "dashboard": (
        '<svg width="12" height="12" viewBox="0 0 16 16">'
        '<rect x="2" y="2" width="5" height="5" stroke="currentColor" stroke-width="1.4" fill="none"/>'
        '<rect x="9" y="2" width="5" height="5" stroke="currentColor" stroke-width="1.4" fill="none"/>'
        '<rect x="2" y="9" width="5" height="5" stroke="currentColor" stroke-width="1.4" fill="none"/>'
        '<rect x="9" y="9" width="5" height="5" stroke="currentColor" stroke-width="1.4" fill="none"/></svg>'
    ),
    "pending": (
        '<svg width="12" height="12" viewBox="0 0 16 16">'
        '<circle cx="8" cy="8" r="3" stroke="currentColor" stroke-width="1.4" fill="none"/>'
        '<circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.4" fill="none" opacity="0.5"/></svg>'
    ),
    "workers": (
        '<svg width="12" height="12" viewBox="0 0 16 16">'
        '<circle cx="4" cy="8" r="2" stroke="currentColor" stroke-width="1.4" fill="none"/>'
        '<circle cx="12" cy="8" r="2" stroke="currentColor" stroke-width="1.4" fill="none"/>'
        '<path d="M6 8 L10 8" stroke="currentColor" stroke-width="1.4"/></svg>'
    ),
    "logs": (
        '<svg width="12" height="12" viewBox="0 0 16 16">'
        '<path d="M3 4 L13 4 M3 8 L13 8 M3 12 L13 12" stroke="currentColor" '
        'stroke-width="1.4" stroke-linecap="round"/></svg>'
    ),
    "specs": (
        '<svg width="12" height="12" viewBox="0 0 16 16">'
        '<path d="M4 2 L10 2 L13 5 L13 14 L4 14 Z" stroke="currentColor" '
        'stroke-width="1.4" fill="none"/>'
        '<path d="M10 2 L10 5 L13 5" stroke="currentColor" '
        'stroke-width="1.4" fill="none"/></svg>'
    ),
}


def icon(name: str) -> str:
    return _ICONS.get(name, "")
