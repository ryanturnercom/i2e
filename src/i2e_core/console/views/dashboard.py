"""Dashboard view — cockpit layout.

Needs-You strip · Shippability + Workers strips · capability cards
grouped by status · Recent ticks. Section IDs are stable for SSE
targeting and the foundation acceptance tests.
"""

from __future__ import annotations

from pathlib import Path

from .. import ui
from ..shell import page
from ..state import ConsoleState, gather, tick_phase

_TITLES = {"active": "Active capabilities", "draft": "Drafts", "shipped": "Shipped"}


def _needs_you(state: ConsoleState) -> str:
    pend = state.pendings
    if not pend:
        return '<section id="needs-you"></section>'
    n = len(pend)
    noun = "item needs" if n == 1 else "items need"
    return f"""<section id="needs-you"><div class="needs-you">
  <div class="row">
    <svg width="14" height="14" viewBox="0 0 16 16">
      <path d="M8 2 L8 9 M8 12 L8 13" stroke="#3d2a72" stroke-width="1.8" stroke-linecap="round"/>
    </svg>
    <span class="ny-label">{n} {noun} attention</span>
  </div>
  <div class="spacer"></div>
  <a class="ny-pill" href="/pending">Open inbox</a>
</div></section>"""


def _shippability(state: ConsoleState) -> str:
    active = state.by_status("active")
    green = sum(1 for c in active if c.shippable)
    if active:
        segs = "".join(
            f'<a class="ship-seg {c.health}" href="/intent/{ui.esc(c.slug)}" '
            f'title="{ui.esc(c.slug)}"></a>'
            for c in active
        )
        bar = f'<div class="ship-bar">{segs}</div>'
    else:
        bar = ui.empty_state("No active capabilities", "Promote a draft to begin")
    legend = (
        '<div class="legend">'
        '<span><span class="sw" style="background:var(--pass-dot)"></span>all green</span>'
        '<span><span class="sw" style="background:var(--lilac-dot)"></span>awaiting human</span>'
        '<span><span class="sw" style="background:var(--trend-dot)"></span>trending</span>'
        '<span><span class="sw" style="background:var(--fail-dot)"></span>failing</span>'
        "</div>"
    )
    regression = (
        '<form hx-post="/api/regression/run" hx-target="#toasts" '
        'hx-swap="beforeend" style="margin-top:14px">'
        '<input type="hidden" name="scope" value="all-shipped">'
        '<button type="submit" class="btn sm outline">'
        "Run regression on all shipped</button></form>"
    )
    return f"""<section id="shippability" class="card p24">
  <div class="card-head">
    <h2 class="h2">Shippability — active capabilities</h2>
    <span class="mono faded">{green} / {len(active)} green</span>
  </div>
  {bar}
  {legend if active else ''}
  {regression}
</section>"""


def _workers_strip(state: ConsoleState) -> str:
    workers = state.workers
    if workers:
        rows = "".join(
            f"""<div class="worker-row">
  <span class="pulse"></span>
  {ui.mono(w.get('capability', ''))}
  <div class="row" style="min-width:0">
    {ui.badge(w.get('step', '—'), 'active', upper=True)}
    {ui.mono(w.get('progress', ''), faded=True)}
  </div>
  {ui.mono(w.get('agent_id', ''), faded=True)}
</div>"""
            for w in workers
        )
        body = rows
    else:
        body = ui.empty_state("Idle", "No workers in flight")
    return f"""<section id="workers" class="card p24">
  <div class="card-head">
    <div class="row">{ui.pulse()}<h2 class="h2">In flight · {len(workers)} parallel</h2></div>
    <a class="mono" href="/workers" style="font-size:11px">Details →</a>
  </div>
  {body}
</section>"""


def _cap_card(cap) -> str:
    c = cap.counts
    total = len(cap.items)
    order = (
        ("pass", "pass"),
        ("trending", "trending"),
        ("awaiting", "awaiting"),
        ("fail", "fail"),
        ("none", "none"),
    )
    segs = "".join(
        f'<div class="seg {cls}" style="flex:{c[key]}"></div>'
        for key, cls in order
        if c[key]
    )
    if not segs:
        segs = '<div class="seg none" style="flex:1"></div>'
    bits = [f"{total} items"]
    if c["fail"]:
        bits.append(f'<span style="color:var(--fail-fg)">{c["fail"]} fail</span>')
    if c["trending"]:
        bits.append(f'<span style="color:var(--trend-fg)">{c["trending"]} trending</span>')
    if c["awaiting"]:
        bits.append(f'<span style="color:var(--lilac-fg)">{c["awaiting"]} awaiting</span>')
    if cap.shippable:
        bits.append('<span style="color:var(--pass-fg);font-weight:600">shippable</span>')
    meta = " · ".join(bits)
    return f"""<a class="cap-card" href="/intent/{ui.esc(cap.slug)}">
  <div class="cc-head">{ui.mono(cap.slug)}{ui.status_badge(cap.status)}</div>
  <div class="cc-title">{ui.esc(cap.title)}</div>
  <div class="ev-bar">{segs}</div>
  <div class="cc-meta">{meta}<span class="push">{ui.esc(ui.relative_time(cap.updated))}</span></div>
</a>"""


def _cap_grid(state: ConsoleState, status: str) -> str:
    caps = sorted(state.by_status(status), key=lambda c: c.slug)
    if not caps:
        return ""
    cards = "".join(_cap_card(c) for c in caps)
    return f"""<div class="section-head">
  {ui.eyebrow(_TITLES.get(status, status))}
  <span style="font-size:11px;color:var(--muted)">· {len(caps)}</span>
</div>
<div class="cap-grid">{cards}</div>"""


def _recent_ticks(state: ConsoleState) -> str:
    ticks = state.ticks[:6]
    if not ticks:
        body = ui.empty_state("No ticks yet", "Run /i2e to drive the loop")
    else:
        rows = []
        for t in ticks:
            first = t.actions[0] if t.actions else "(no actions)"
            extra = (
                f' <span style="color:var(--muted)">+{len(t.actions) - 1} more</span>'
                if len(t.actions) > 1
                else ""
            )
            rows.append(
                f"""<div class="tick-row">
  {ui.phase_pill(tick_phase(t))}
  {ui.mono(t.tick_id[-6:])}
  <div class="tr-summary">{ui.esc(first)}{extra}</div>
  {ui.mono(ui.relative_time(t.ran_at), faded=True)}
</div>"""
            )
        body = "".join(rows)
    return f"""<section id="recent-ticks" class="card p24">
  <h2 class="h2" style="margin-bottom:14px">Recent ticks</h2>
  {body}
</section>"""


def dashboard_body(state: ConsoleState) -> str:
    grids = "".join(_cap_grid(state, s) for s in ("active", "draft", "shipped"))
    if not grids:
        grids = ui.empty_state(
            "No capabilities yet", "Author an intent with i2e-intent"
        )
    needs = _needs_you(state)
    ship = _shippability(state)
    workers = _workers_strip(state)
    ticks = _recent_ticks(state)
    caps = f'<section id="capabilities">{grids}</section>'

    blocks = [
        needs,
        f'<div class="grid-2-1">{ship}{workers}</div>',
        caps,
        ticks,
    ]
    return f'<div class="stack" id="dashboard">{"".join(blocks)}</div>'


def render_dashboard(
    root: Path,
    *,
    flt: str | None = None,
    q: str | None = None,
    cookie: str | None = None,
) -> str:
    state = gather(Path(root))
    return page(
        root=Path(root),
        active="dashboard",
        state=state,
        eyebrow="Dashboard",
        title="Operator view",
        path="/",
        sidebar_filter=flt,
        sidebar_q=q,
        cookie=cookie,
        body=dashboard_body(state),
    )
