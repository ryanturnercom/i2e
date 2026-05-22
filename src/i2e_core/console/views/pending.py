"""Pending view — `/pending`.

Open pending files grouped into Human evaluations and Escalations, with
watcher summary chips and an inline resolve form per card. The form
POSTs to ``/api/pending/<file>/resolve``; the resolution is applied on
the next ``i2e-adapt`` tick.
"""

from __future__ import annotations

from pathlib import Path

from .. import ui
from ..shell import page
from ..state import ConsoleState, PendingView, gather


def _resolve_form(p: PendingView) -> str:
    opts = "".join(
        f'<label class="verdict-opt"><input type="radio" name="verdict" '
        f'value="{ui.esc(o)}"{" checked" if i == 0 else ""}>'
        f"<span>{ui.esc(o)}</span></label>"
        for i, o in enumerate(p.verdict_options)
    )
    return f"""<form class="resolve-form" hx-post="/api/pending/{ui.esc(p.file)}/resolve"
    hx-target="closest .pending-card" hx-swap="outerHTML">
  <div class="rf-label">{ui.eyebrow("Your verdict")}</div>
  <div class="verdict-opts">{opts}</div>
  <div class="rf-label">{ui.eyebrow("Notes (optional)")}</div>
  <textarea name="notes" rows="2" placeholder="What did you observe?"></textarea>
  <button type="submit" class="btn">Write resolution</button>
  <span class="mono faded" style="margin-left:10px;font-size:11px">queued · applied next tick</span>
</form>"""


def _card(p: PendingView) -> str:
    is_escalation = p.kind != "human_evaluation"
    kind_badge = (
        ui.badge("escalation", "fail", upper=True)
        if is_escalation
        else ui.badge("human evaluation", "awaiting_human", upper=True)
    )
    dotcolor = "var(--fail-dot)" if is_escalation else "var(--lilac-dot)"
    kv = ""
    rows = []
    if p.expect:
        rows.append(f"{ui.mono('expect', faded=True)}{ui.mono(p.expect)}")
    if p.observed:
        rows.append(f"{ui.mono('observed', faded=True)}{ui.mono(p.observed)}")
    if rows:
        kv = f'<div class="pc-kv">{"".join(rows)}</div>'
    return f"""<article class="pending-card" data-file="{ui.esc(p.file)}"
  data-kind="{ui.esc(p.kind)}" data-capability="{ui.esc(p.capability)}"
  data-item-id="{ui.esc(p.item_id)}" data-watcher="{ui.esc(p.watcher)}">
  <div class="pc-head">
    <div class="pc-id">
      <span class="dot" style="background:{dotcolor}"></span>
      {ui.mono(p.capability)}{ui.mono("/ " + p.item_id, faded=True)}
    </div>
    <div class="row">{kind_badge}{ui.mono(ui.relative_time(p.asked_at), faded=True)}</div>
  </div>
  <div class="pc-ask">{ui.esc(p.ask)}</div>
  {kv}
  <div class="pc-foot">
    {ui.mono(p.watcher, faded=True)}
    {ui.mono("·", faded=True)}
    {ui.mono(".i2e/pending/" + p.file, faded=True)}
  </div>
  {_resolve_form(p)}
</article>"""


def _section(title: str, note: str, items: list[PendingView]) -> str:
    if not items:
        return ""
    cards = "".join(_card(p) for p in items)
    return f"""<div>
  <div class="section-head">{ui.eyebrow(title)}
    <span style="font-size:11px;color:var(--muted)">· {note}</span></div>
  <div class="stack">{cards}</div>
</div>"""


def pending_body(state: ConsoleState) -> str:
    pend = state.pendings
    evals = [p for p in pend if p.kind == "human_evaluation"]
    escalations = [p for p in pend if p.kind != "human_evaluation"]

    by_watcher: dict[str, int] = {}
    for p in pend:
        by_watcher[p.watcher] = by_watcher.get(p.watcher, 0) + 1
    chips = "".join(
        f'<div class="watcher-chip"><span class="wc-name">{ui.esc(w)}</span>'
        f'<span class="wc-count">{n}</span></div>'
        for w, n in sorted(by_watcher.items())
    )
    chips_html = f'<div class="watcher-chips">{chips}</div>' if chips else ""

    intro = f"""<div>
  {ui.eyebrow("Pending")}
  <h1 class="h1">What needs a human</h1>
  <div class="lead">All open items in <span class="mono">.i2e/pending/</span>.
  {len(evals)} evaluations, {len(escalations)} escalations.</div>
</div>"""

    if not pend:
        return f'<div class="stack" id="pending-view">{intro}' + (
            ui.empty_state("Inbox zero", "Nothing is waiting on a human") + "</div>"
        )

    return f"""<div class="stack" id="pending-view">
  {intro}
  <section id="watcher-summary">{chips_html}</section>
  <section id="human-evaluations">{_section("Human evaluations", f"{len(evals)} · provider: human", evals)}</section>
  <section id="escalations">{_section("Escalations", f"{len(escalations)} · budgets exhausted", escalations)}</section>
</div>"""


def render_pending(root: Path, *, cookie: str | None = None) -> str:
    root = Path(root)
    state = gather(root)
    return page(
        root=root,
        active="pending",
        state=state,
        eyebrow="Pending",
        title="Inbox",
        path="/pending",
        cookie=cookie,
        body=pending_body(state),
    )
