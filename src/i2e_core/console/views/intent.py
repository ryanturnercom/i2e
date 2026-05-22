"""Intent detail view — `/intent/<slug>`.

Split layout: evidence + run history + source on the left, a sticky
status/meta rail on the right. The Promote button POSTs to
``/api/intents/<slug>/promote``; the console never edits intent bodies.
"""

from __future__ import annotations

from pathlib import Path

from .. import ui
from ..prefs import parse_prefs_from_cookie
from ..shell import page
from ..state import ConsoleState, CapView, gather, tick_phase


def _ev_row(item) -> str:
    sub = (
        f'<div class="ev-sub">{ui.mono(item.provider, faded=True)}'
        f'<span>·</span>{ui.mono(item.query, faded=True)}</div>'
    )
    value = (
        f'<div style="font-size:11px;color:var(--text);margin-top:4px">{ui.esc(item.value)}</div>'
        if item.value
        else ""
    )
    return f"""<div class="ev-row">
  <div class="ev-grid">
    {ui.type_badge(item.type)}
    <div style="min-width:0">{ui.mono(item.id)}{sub}</div>
    {ui.effort_pip(item.effort, item.attempts_used)}
    <div class="ev-verdict">{ui.verdict_badge(item.verdict)}{value}</div>
  </div>
</div>"""


def _evidence_section(cap: CapView) -> str:
    ev_rows = "".join(_ev_row(it) for it in cap.evidence) or (
        '<div class="ev-row"><span class="mono faded">No evidence items.</span></div>'
    )
    cn = ""
    if cap.constraints:
        cn_rows = "".join(_ev_row(it) for it in cap.constraints)
        cn = f"""<div class="ev-section-head constraints">
  <div class="card-head" style="margin:0"><h2 class="h2">Constraints</h2>
  <span class="mono faded">{len(cap.constraints)} items</span></div>
</div>{cn_rows}"""
    return f"""<section id="evidence-table" class="card p0">
  <div class="ev-section-head">
    <div class="card-head" style="margin:0"><h2 class="h2">Evidence of success</h2>
    <span class="mono faded">{len(cap.evidence)} items</span></div>
  </div>
  {ev_rows}
  {cn}
</section>"""


def _status_action(cap: CapView, demotable: bool) -> str:
    """The single status-transition control shown in the meta card."""
    if cap.status == "draft":
        return (
            '<button id="promote-button" class="btn" '
            f'hx-post="/api/intents/{ui.esc(cap.slug)}/promote" '
            'hx-target="#status-result" hx-swap="innerHTML">Promote → active</button>'
        )
    if cap.status == "active":
        disabled = "" if demotable else " disabled"
        hint = (
            ""
            if demotable
            else '<div class="mono faded" style="margin-top:6px;font-size:11px">'
            "started — demote only applies to un-started intents</div>"
        )
        return (
            '<button id="demote-button" class="btn outline" '
            f'hx-post="/api/intents/{ui.esc(cap.slug)}/demote" '
            f'hx-target="#status-result" hx-swap="innerHTML"{disabled}>'
            "Demote → draft</button>" + hint
        )
    if cap.status == "shipped":
        return (
            '<form hx-post="/api/regression/run" hx-target="#toasts" '
            'hx-swap="beforeend">'
            f'<input type="hidden" name="scope" value="slug:{ui.esc(cap.slug)}">'
            '<button type="submit" class="btn outline">Re-validate · regression</button>'
            "</form>"
            '<div class="mono faded" style="margin-top:6px;font-size:11px">'
            "re-runs i2e-regression; demotes to active on any flip</div>"
        )
    return (
        '<div class="mono faded" style="font-size:11px">'
        "status is managed by the orchestrator / i2e-intent</div>"
    )


def _meta_card(cap: CapView, demotable: bool) -> str:
    chips_dep = ""
    if cap.depends_on:
        chips = "".join(ui.code_chip(d) for d in cap.depends_on)
        chips_dep = (
            f'{ui.eyebrow("Depends on")}<div class="mc-chips">{chips}</div>'
        )
    chips_touch = ""
    if cap.touches:
        chips = "".join(ui.code_chip(t) for t in cap.touches)
        chips_touch = f'{ui.eyebrow("Touches")}<div class="mc-chips">{chips}</div>'
    spec = ""
    if cap.spec:
        section = f" §{ui.esc(cap.spec_section)}" if cap.spec_section else ""
        spec = (
            f'{ui.eyebrow("Source spec")}'
            f'<div class="mc-val">{ui.mono(f".i2e/specs/{cap.spec}.md{section}")}</div>'
        )
    shippable = ui.badge("shippable", "pass") if cap.shippable else ""
    return f"""<aside id="meta" class="card p24 meta-card">
  {ui.eyebrow("Status")}
  <div class="row" style="margin:8px 0 16px">{ui.status_badge(cap.status)}{shippable}</div>
  {_status_action(cap, demotable)}
  <div id="status-result" aria-live="polite" style="margin-top:10px"></div>
  <div style="height:18px"></div>
  {ui.eyebrow("Owner")}<div class="mc-val">{ui.esc(cap.watcher)}</div>
  {ui.eyebrow("Version")}<div class="mc-val">{ui.mono("v" + str(cap.version))}
    <span class="mono faded">updated {ui.esc(cap.updated)}</span></div>
  {chips_dep}{chips_touch}{spec}
</aside>"""


def _inflight_strip(state: ConsoleState, cap: CapView) -> str:
    workers = state.workers_for(cap.slug)
    if not workers:
        return ""
    rows = "".join(
        f'<div class="row" style="font-size:12px">{ui.mono(w.get("agent_id", ""))}'
        f'{ui.mono(w.get("progress", ""), faded=True)}</div>'
        for w in workers
    )
    plural = "s" if len(workers) > 1 else ""
    return f"""<div class="inflight-strip">
  <div class="is-head">{ui.pulse(variant="white")}
    {len(workers)} worker{plural} running on this intent</div>
  {rows}
</div>"""


def _pending_strip(state: ConsoleState, cap: CapView) -> str:
    pend = state.pendings_for(cap.slug)
    if not pend:
        return ""
    rows = "".join(
        f"""<div class="ps-row">
  <div style="min-width:0">{ui.mono(p.item_id)}
    <div class="ps-ask">{ui.esc(p.ask.splitlines()[0] if p.ask else "")}</div></div>
  <a class="btn sm" href="/pending">Resolve</a>
</div>"""
        for p in pend
    )
    return f"""<div class="pending-strip">
  <div class="ps-head">{len(pend)} pending — needs human</div>
  {rows}
</div>"""


def _run_history(state: ConsoleState, cap: CapView) -> str:
    mine = [t for t in state.ticks if any(cap.slug in a for a in t.actions)][:8]
    if not mine:
        return ""
    rows = "".join(
        f"""<div class="tick-row">
  {ui.phase_pill(tick_phase(t))}
  {ui.mono(t.tick_id[-12:])}
  <div class="tr-summary">{ui.esc(t.actions[0] if t.actions else "")}</div>
  {ui.mono(ui.relative_time(t.ran_at), faded=True)}
</div>"""
        for t in mine
    )
    return f"""<section class="card p24">
  <div class="card-head"><h2 class="h2">Run history</h2>
  <span class="mono faded">last {len(mine)} ticks</span></div>
  {rows}
</section>"""


def _source_block(cap: CapView) -> str:
    return f"""<section class="card p0 source-block">
  <div class="sb-bar">
    {ui.mono(f".i2e/intents/{cap.slug}.md")}
    <span class="push mono faded" style="font-size:11px">read-only · Edit via i2e-intent</span>
  </div>
  <pre>{ui.esc(cap.source)}</pre>
</section>"""


def render_intent_detail(
    root: Path, slug: str, *, cookie: str | None = None
) -> str:
    root = Path(root)
    state = gather(root)
    cap = state.cap(slug)
    if cap is None:
        return page(
            root=root,
            active="intent",
            state=state,
            eyebrow="Intent",
            title=slug,
            selected_slug=slug,
            path=f"/intent/{slug}",
            cookie=cookie,
            body=f'<div data-slug="{ui.esc(slug)}">'
            + ui.empty_state("Intent not found", slug)
            + "</div>",
        )
    layout = parse_prefs_from_cookie(cookie).get("intent", "split")

    header = f"""<div class="intent-head">
  <div class="ih-path">{ui.mono(".i2e/intents/", faded=True)}{ui.mono(cap.slug + ".md")}</div>
  <h1 class="h1">{ui.esc(cap.title)}</h1>
  {f'<div class="lead">{ui.esc(cap.summary)}</div>' if cap.summary else ''}
</div>"""

    left = (
        _evidence_section(cap)
        + _run_history(state, cap)
        + _source_block(cap)
    )
    demotable = (
        cap.status == "active"
        and not cap.started
        and not state.workers_for(cap.slug)
    )
    data_attrs = (
        f'data-slug="{ui.esc(cap.slug)}" data-status="{ui.esc(cap.status)}"'
    )
    if layout == "single":
        detail = f"""<div {data_attrs}>
    <div id="primary" class="stack">{_meta_card(cap, demotable)}{left}</div>
  </div>"""
    else:
        detail = f"""<div class="split" {data_attrs}>
    <div id="primary" class="stack">{left}</div>
    <div class="rail">{_meta_card(cap, demotable)}</div>
  </div>"""
    body = f"""<div class="stack">
  {header}
  {_inflight_strip(state, cap)}
  {_pending_strip(state, cap)}
  {detail}
</div>"""

    return page(
        root=root,
        active="intent",
        state=state,
        eyebrow=cap.slug,
        title=cap.title,
        selected_slug=slug,
        path=f"/intent/{slug}",
        cookie=cookie,
        body=body,
    )
