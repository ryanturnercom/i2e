"""Logs view — `/logs`.

Append-only tick history. Timeline (default) and table modes; a phase
filter and a free-text filter narrow the list. Each tick expands to its
full action list.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from .. import ui
from ..prefs import parse_prefs_from_cookie
from ..shell import page
from ..state import ConsoleState, gather, tick_phase

LogsMode = Literal["timeline", "table"]
_PHASES = ("all", "intent", "develop", "evidence", "adapt")


def _filter_ticks(state: ConsoleState, phase: str | None, q: str | None):
    ticks = list(state.ticks)
    if phase and phase != "all":
        ticks = [t for t in ticks if tick_phase(t) == phase]
    if q:
        needle = q.strip().lower()
        ticks = [
            t
            for t in ticks
            if needle in t.tick_id.lower()
            or any(needle in a.lower() for a in t.actions)
        ]
    return ticks


def _toolbar(mode: str, phase: str | None, q: str | None) -> str:
    active_phase = phase or "all"
    qarg = f"&q={ui.esc(q)}" if q else ""
    phase_chips = "".join(
        f'<a class="{"active" if p == active_phase else ""}" '
        f'href="/logs?mode={mode}&phase={p}{qarg}">{p}</a>'
        for p in _PHASES
    )
    modes = "".join(
        f'<a class="{"active" if m == mode else ""}" '
        f'href="/logs?mode={m}&phase={active_phase}{qarg}">{m}</a>'
        for m in ("timeline", "table")
    )
    return f"""<section class="card p16">
  <div class="logs-toolbar">
    <div class="seg-toggle">{phase_chips}</div>
    <form method="get" action="/logs" style="flex:1;min-width:200px">
      <input type="hidden" name="mode" value="{mode}">
      <input type="hidden" name="phase" value="{active_phase}">
      <input type="text" name="q" value="{ui.esc(q or '')}" placeholder="filter by slug or tick-id"
        style="width:100%;box-sizing:border-box;background:#fff;border:1px solid var(--border);
        border-radius:6px;padding:6px 10px;font-family:inherit;font-size:12px;outline:none">
    </form>
    <div class="seg-toggle">{modes}</div>
  </div>
</section>"""


def _timeline(ticks) -> str:
    items = []
    for t in ticks:
        actions = "".join(
            f'<div class="mono" style="font-size:12px'
            f'{";color:var(--muted)" if i else ""}">{ui.esc(a)}</div>'
            for i, a in enumerate(t.actions)
        )
        when = ui.relative_time(t.ran_at)
        clock = t.ran_at.strftime("%H:%M") if t.ran_at else ""
        items.append(
            f"""<li class="timeline-item">
  <div class="tl-time">{ui.mono(when)}<span class="mono faded" style="display:block">{ui.esc(clock)}</span></div>
  <div class="tl-rail">{ui.phase_pill(tick_phase(t))}</div>
  <div class="tl-card"><div class="card">
    {ui.mono(t.tick_id)}
    <div class="tl-actions">{actions}</div>
  </div></div>
</li>"""
        )
    return f'<ol class="timeline">{"".join(items)}</ol>'


def _table(ticks) -> str:
    rows = []
    for t in ticks:
        first = t.actions[0] if t.actions else "(no actions)"
        rows.append(
            f"""<tr>
  <td>{ui.phase_pill(tick_phase(t))}</td>
  <td>{ui.mono(t.tick_id)}</td>
  <td>{ui.mono(first)}</td>
  <td>{ui.mono(len(t.actions), faded=True)}</td>
  <td>{ui.mono(ui.relative_time(t.ran_at), faded=True)}</td>
</tr>"""
        )
    return f"""<table class="logs-table"><thead><tr>
  <th></th><th>Tick</th><th>Action</th><th>Count</th><th>When</th>
</tr></thead><tbody>{"".join(rows)}</tbody></table>"""


def logs_body(state: ConsoleState, mode: str, phase: str | None, q: str | None) -> str:
    ticks = _filter_ticks(state, phase, q)
    intro = f"""<div>
  {ui.eyebrow("Logs")}
  <h1 class="h1">Tick history</h1>
  <div class="lead">Append-only. <span class="mono">.i2e/logs/</span> stores one
  yaml per non-empty tick. Empty ticks don't log.</div>
</div>"""
    if not ticks:
        body = '<section class="card">' + ui.empty_state(
            "No ticks match", "Try clearing the filter"
        ) + "</section>"
    elif mode == "table":
        body = f'<section class="card p0">{_table(ticks)}</section>'
    else:
        body = _timeline(ticks)
    return f"""<div class="stack" id="logs-view" data-mode="{mode}">
  {intro}
  {_toolbar(mode, phase, q)}
  {body}
</div>"""


def render_logs(
    root: Path,
    mode: LogsMode | None = None,
    *,
    phase: str | None = None,
    q: str | None = None,
    cookie: str | None = None,
) -> str:
    # Mode falls back to the Tweaks-panel default when not given explicitly.
    if mode is None:
        mode = parse_prefs_from_cookie(cookie).get("logs", "timeline")
    if mode not in ("timeline", "table"):
        mode = "timeline"
    root = Path(root)
    state = gather(root)
    return page(
        root=root,
        active="logs",
        state=state,
        eyebrow="Logs",
        title="Tick history",
        path="/logs",
        cookie=cookie,
        body=logs_body(state, mode, phase, q),
    )
