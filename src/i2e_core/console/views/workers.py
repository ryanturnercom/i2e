"""Workers view — `/workers`.

Read-only. One card per ``.i2e/worktrees/<slug>/claim.json`` with the
claim fields and a live log tail. The console observes worker lifecycle;
it never spawns, kills, or reassigns a worker.
"""

from __future__ import annotations

from pathlib import Path

from .. import ui
from ..shell import page
from ..state import ConsoleState, gather

_CLAIM_FIELDS = (
    ("capability", "capability"),
    ("agent_id", "agent"),
    ("session_id", "session"),
    ("pid", "pid"),
    ("tick_id", "tick"),
    ("worktree", "worktree"),
)


def _log_tail(lines: list[str]) -> str:
    if not lines:
        body = '<div class="log-line"><span class="ln">··</span><span>no log output yet</span></div>'
    else:
        body = "".join(
            f'<div class="log-line"><span class="ln">{str(i + 1).zfill(2)}</span>'
            f"<span>{ui.esc(ln)}</span></div>"
            for i, ln in enumerate(lines)
        )
    return f'<pre class="log-tail" data-strip="log-tail">{body}</pre>'


def _card(w: dict) -> str:
    kv = "".join(
        f"{ui.mono(label, faded=True)}{ui.mono(w.get(key, '—'))}"
        for key, label in _CLAIM_FIELDS
        if w.get(key) not in (None, "")
    )
    step = w.get("step", "—")
    started = w.get("started_at", "")
    progress = w.get("progress", "")
    return f"""<article class="worker-card" data-capability="{ui.esc(w.get('capability', ''))}"
  data-agent="{ui.esc(w.get('agent_id', ''))}" data-step="{ui.esc(step)}">
  <div class="card-head" style="margin-bottom:14px">
    <div class="row">{ui.pulse()}{ui.mono(w.get('agent_id', ''), cls='')}
      {ui.badge(step, 'active', upper=True)}</div>
    {ui.mono("started " + ui.relative_time(started) if started else "", faded=True)}
  </div>
  <div class="wk-kv">{kv}</div>
  {ui.eyebrow("Current step")}
  <div class="wk-step">{ui.esc(progress) or "—"}</div>
  {ui.eyebrow("Live log")}
  <div style="height:8px"></div>
  {_log_tail(w.get('_log_tail', []))}
  <div style="font-size:11px;color:var(--muted);margin-top:6px">
    started_at {ui.esc(started)}</div>
</article>"""


def workers_body(state: ConsoleState) -> str:
    workers = state.workers
    intro = f"""<div>
  {ui.eyebrow("Workers")}
  <h1 class="h1">{len(workers)} {"worker" if len(workers) == 1 else "workers"} in flight</h1>
  <div class="lead">Each lock under <span class="mono">.i2e/worktrees/&lt;slug&gt;/</span>
  claims a capability for the current tick.</div>
</div>"""
    if not workers:
        return (
            f'<div class="stack" id="workers-view">{intro}'
            '<section class="card">'
            + ui.empty_state(
                "No workers in flight",
                "The orchestrator is idle — the next tick starts at the top of the decision tree.",
            )
            + "</section></div>"
        )
    cards = "".join(_card(w) for w in workers)
    return f"""<div class="stack" id="workers-view">
  {intro}
  <div class="cap-grid">{cards}</div>
</div>"""


def render_workers(root: Path, *, cookie: str | None = None) -> str:
    root = Path(root)
    state = gather(root)
    return page(
        root=root,
        active="workers",
        state=state,
        eyebrow="Workers",
        title="In flight",
        path="/workers",
        cookie=cookie,
        body=workers_body(state),
    )
