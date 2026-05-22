"""State-to-view-model mapper for the i2e-report renderer.

Reads from disk and produces a fully-serializable :class:`ReportViewModel`
that is fed into the Jinja2 template. The mapper is deterministic — same
inputs → same outputs (stable sort order everywhere).

The :func:`render` function reads state, builds the view model, and writes
``.i2e/report.html`` atomically. It is the public entry point used by the
orchestrator.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jinja2
from pydantic import BaseModel, ConfigDict, Field

from ..config import I2EConfig, load_config, resolve_max_attempts
from ..evidence import CurrentEvidence, ItemVerdict, read_current
from ..intent import Capability, parse_intent
from ..io_utils import atomic_write
from ..paths import (
    intents_dir,
    logs_dir,
    pending_dir,
    report_path,
    serve_url_path,
)
from ..pending import PendingFile, list_open_pending, read_pending
from ..swarm import Claim, is_pid_alive, read_claim, worktrees_root
from ..tick_log import TickLog, _read_tick


# ---------- Pydantic view models ----------


_GREEN_VERDICTS = frozenset({"pass", "met"})
_FAILURE_VERDICTS = frozenset({"fail", "unmet"})
_NOTIFICATION_KIND_ORDER = {
    "failure": 0,
    "pending": 1,
    "trending": 2,
    "intervention": 3,
}

_VERDICT_LABEL = {
    "pass": "pass",
    "fail": "fail",
    "met": "met",
    "unmet": "unmet",
    "trending": "trending",
    "awaiting_human": "awaiting",
}

_VERDICT_CLASS = {
    "pass": "pass",
    "fail": "fail",
    "met": "met",
    "unmet": "unmet",
    "trending": "trending",
    "awaiting_human": "awaiting",
}


class ItemView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    provider: str
    query: str = ""
    expect: str = ""
    verdict: str
    verdict_label: str
    verdict_class: str
    value: str | None = None
    attempts_used: int = 0
    max_attempts: int = 0
    last_observed: str | None = None
    pending_basename: str | None = None


class CapabilityView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    version: int
    status: str
    watcher: str
    items: list[ItemView] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)

    @property
    def summary_sorted(self) -> list[tuple[str, int]]:
        return sorted(self.summary.items())


class PendingView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str
    kind: str
    capability: str
    item_id: str
    ask: str
    verdict_options: list[str] = Field(default_factory=list)
    attempts: list[dict[str, Any]] = Field(default_factory=list)
    status: str
    resolution_template: str = ""


class InFlightView(BaseModel):
    """One active worktree claim — the live row in the in-flight panel."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    step: str
    agent_id: str
    session_id: str | None = None
    tick_id: str
    started_at: str
    progress: str = ""
    alive: bool = True


class NotificationView(BaseModel):
    """One row in the watcher notifications surface.

    ``kind`` is the high-level category — ``failure`` (verdict=fail/unmet),
    ``trending`` (verdict=trending, not yet failing but slipping),
    ``pending`` (an open pending file awaiting the watcher), or
    ``intervention`` (a target verdict signalling human intervention is
    needed). The ``href`` is a fragment that scrolls to the source so the
    watcher can act in one click.
    """

    model_config = ConfigDict(extra="forbid")

    kind: str
    watcher: str
    capability: str
    item_id: str
    message: str
    href: str


class ParallelismView(BaseModel):
    """Roll-up of how many agents are running in parallel right now."""

    model_config = ConfigDict(extra="forbid")

    parallel_count: int = 0
    distinct_agents: int = 0
    by_step: dict[str, int] = Field(default_factory=dict)

    @property
    def by_step_sorted(self) -> list[tuple[str, int]]:
        return sorted(self.by_step.items())


class TickView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tick_id: str
    ran_at: str
    actions: list[str] = Field(default_factory=list)


class ReportViewModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_name: str
    generated_at: datetime
    generated_at_display: str
    last_tick_id: str | None = None
    shippable: bool
    capabilities: list[CapabilityView] = Field(default_factory=list)
    drafts: list[CapabilityView] = Field(default_factory=list)
    shipped: list[CapabilityView] = Field(default_factory=list)
    in_flight: list[InFlightView] = Field(default_factory=list)
    parallelism: ParallelismView = Field(default_factory=ParallelismView)
    notifications: list[NotificationView] = Field(default_factory=list)
    pending: list[PendingView] = Field(default_factory=list)
    ticks: list[TickView] = Field(default_factory=list)
    serve_url: str | None = None


# ---------- Builders ----------


def _read_serve_url(root: Path) -> str | None:
    p = serve_url_path(Path(root))
    if not p.exists():
        return None
    try:
        return p.read_text(encoding="utf-8").strip() or None
    except Exception:
        return None


def _format_dt(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%SZ")


def _list_capabilities_by_status(
    root: Path, status: str
) -> list[Capability]:
    base = intents_dir(Path(root))
    if not base.exists():
        return []
    out: list[Capability] = []
    for path in sorted(base.glob("*.md")):
        try:
            cap = parse_intent(path)
        except Exception:
            continue
        if cap.frontmatter.status == status:
            out.append(cap)
    out.sort(key=lambda c: c.frontmatter.capability)
    return out


def _list_active_capabilities(root: Path) -> list[Capability]:
    return _list_capabilities_by_status(root, "active")


def _list_draft_capabilities(root: Path) -> list[Capability]:
    return _list_capabilities_by_status(root, "draft")


def _list_shipped_capabilities(root: Path) -> list[Capability]:
    return _list_capabilities_by_status(root, "shipped")


def _build_item_view(
    item_id: str,
    item_type: str,
    provider: str,
    effort: str,
    cfg: I2EConfig,
    verdict: ItemVerdict | None,
    query: str = "",
    expect: str = "",
) -> ItemView:
    try:
        max_attempts = resolve_max_attempts(cfg, item_type, effort)  # type: ignore[arg-type]
    except Exception:
        max_attempts = 0

    if verdict is None:
        return ItemView(
            id=item_id,
            type=item_type,
            provider=provider,
            query=query,
            expect=expect,
            verdict="none",
            verdict_label="no data",
            verdict_class="none",
            value=None,
            attempts_used=0,
            max_attempts=max_attempts,
            last_observed=None,
            pending_basename=None,
        )

    return ItemView(
        id=item_id,
        type=item_type,
        provider=provider,
        query=query,
        expect=expect,
        verdict=verdict.verdict,
        verdict_label=_VERDICT_LABEL.get(verdict.verdict, verdict.verdict),
        verdict_class=_VERDICT_CLASS.get(verdict.verdict, "none"),
        value=verdict.value,
        attempts_used=verdict.attempts_used,
        max_attempts=max_attempts,
        last_observed=_format_dt(verdict.last_observed),
        pending_basename=verdict.pending,
    )


def _build_capability_view(
    cap: Capability, cur: CurrentEvidence | None, cfg: I2EConfig
) -> CapabilityView:
    items: list[ItemView] = []
    current_items: dict[str, ItemVerdict] = cur.items if cur else {}

    # Combine evidence + constraints, sorted by id.
    spec_items: list[tuple[str, str, str, str, str, str]] = []
    for ev in cap.evidence:
        spec_items.append(
            (ev.id, ev.type, ev.provider, ev.effort, ev.query, ev.expect)
        )
    for cn in cap.constraints:
        spec_items.append(
            (cn.id, "constraint", cn.provider, cn.effort, cn.query, cn.expect)
        )
    spec_items.sort(key=lambda t: t[0])

    for item_id, item_type, provider, effort, query, expect in spec_items:
        verdict = current_items.get(item_id)
        items.append(
            _build_item_view(
                item_id, item_type, provider, effort, cfg, verdict,
                query=query, expect=expect,
            )
        )

    # Summary by verdict label.
    summary: dict[str, int] = {}
    for iv in items:
        summary[iv.verdict] = summary.get(iv.verdict, 0) + 1

    return CapabilityView(
        slug=cap.frontmatter.capability,
        version=cap.frontmatter.version,
        status=cap.frontmatter.status,
        watcher=cap.frontmatter.watcher,
        items=items,
        summary=summary,
    )


def _resolution_template(pf: PendingFile) -> str:
    """Render a deterministic resolution-textarea hint.

    Shows the existing resolution if set, otherwise an empty placeholder.
    """
    if pf.resolution:
        return pf.resolution
    if pf.verdict_options:
        return ""
    return ""


def _build_pending_view(path: Path) -> PendingView | None:
    try:
        pf = read_pending(path)
    except Exception:
        return None
    return PendingView(
        filename=path.name,
        kind=pf.kind,
        capability=pf.capability,
        item_id=pf.item_id,
        ask=pf.ask,
        verdict_options=list(pf.verdict_options or []),
        attempts=list(pf.attempts or []),
        status=pf.status,
        resolution_template=_resolution_template(pf),
    )


def _build_notifications(
    capabilities: list[CapabilityView],
    pending_views: list[PendingView],
    raw_caps: list[Capability],
) -> list[NotificationView]:
    """Roll up everything that needs a watcher's attention.

    The watcher must land on the page and immediately see "what needs me?" —
    so we surface failures, trending items, pending asks, and target
    interventions in one place, sorted by severity then by watcher.
    """
    watcher_by_slug = {c.frontmatter.capability: c.frontmatter.watcher for c in raw_caps}
    out: list[NotificationView] = []
    for cap in capabilities:
        watcher = watcher_by_slug.get(cap.slug, cap.watcher)
        for item in cap.items:
            if item.verdict in _FAILURE_VERDICTS:
                kind = "failure"
                msg = (
                    f"{item.type} {item.id} is {item.verdict_label}"
                    + (f" ({item.value})" if item.value else "")
                )
                out.append(
                    NotificationView(
                        kind=kind,
                        watcher=watcher,
                        capability=cap.slug,
                        item_id=item.id,
                        message=msg,
                        href=f"#item/{cap.slug}/{item.id}",
                    )
                )
            elif item.verdict == "trending":
                out.append(
                    NotificationView(
                        kind="trending",
                        watcher=watcher,
                        capability=cap.slug,
                        item_id=item.id,
                        message=f"target {item.id} is trending — heading toward unmet",
                        href=f"#item/{cap.slug}/{item.id}",
                    )
                )
            elif item.verdict == "awaiting_human" and item.type == "target":
                out.append(
                    NotificationView(
                        kind="intervention",
                        watcher=watcher,
                        capability=cap.slug,
                        item_id=item.id,
                        message=f"target {item.id} needs human intervention",
                        href=f"#item/{cap.slug}/{item.id}",
                    )
                )
    for p in pending_views:
        watcher = watcher_by_slug.get(p.capability, "@me")
        out.append(
            NotificationView(
                kind="pending",
                watcher=watcher,
                capability=p.capability,
                item_id=p.item_id,
                message=f"awaiting human: {p.ask}",
                href=f"#pending/{p.filename}",
            )
        )
    out.sort(
        key=lambda n: (
            _NOTIFICATION_KIND_ORDER.get(n.kind, 99),
            n.watcher,
            n.capability,
            n.item_id,
        )
    )
    return out


def _list_in_flight(root: Path) -> list[InFlightView]:
    """Read every live worktree claim under ``.i2e/worktrees/``.

    A worktree directory without a parsable ``claim.json`` is skipped (it's
    in the process of being acquired or released). Claims whose pid is not
    alive are still surfaced but flagged ``alive=False`` so the operator
    can see something is stuck.
    """
    base = worktrees_root(Path(root))
    if not base.exists():
        return []
    out: list[InFlightView] = []
    for sub in sorted(base.iterdir()):
        if not sub.is_dir():
            continue
        claim = read_claim(root, sub.name)
        if claim is None:
            continue
        out.append(
            InFlightView(
                slug=claim.slug,
                step=claim.step,
                agent_id=claim.agent_id,
                session_id=claim.session_id,
                tick_id=claim.tick_id,
                started_at=_format_dt(claim.started_at) or "",
                progress=claim.progress,
                alive=is_pid_alive(claim.pid),
            )
        )
    out.sort(key=lambda v: (v.slug, v.started_at))
    return out


def _list_recent_ticks(root: Path, n: int = 10) -> list[tuple[Path, TickLog]]:
    base = logs_dir(Path(root))
    if not base.exists():
        return []
    parsed: list[tuple[Path, TickLog]] = []
    for p in base.glob("*-tick.yaml"):
        if not p.is_file():
            continue
        tl = _read_tick(p)
        if tl is not None:
            parsed.append((p, tl))
    # Reverse chronological by ran_at. Filename sort is unreliable within a day
    # because the run-id hex suffix is random. Tiebreak by filename for stability.
    parsed.sort(key=lambda pair: (pair[1].ran_at, pair[0].name), reverse=True)
    return parsed[:n]


def _build_tick_view(tl: TickLog) -> TickView:
    return TickView(
        tick_id=tl.tick_id,
        ran_at=_format_dt(tl.ran_at) or "",
        actions=list(tl.actions),
    )


def _generated_at(root: Path, ticks: list[tuple[Path, TickLog]]) -> datetime:
    """Derive a deterministic generated_at — newest tick's ran_at if any.

    Falls back to a stable sentinel (epoch UTC) when there are no ticks so
    that a no-tick project still produces byte-identical output across runs.
    """
    if ticks:
        dt = ticks[0][1].ran_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def build_view_model(root: Path) -> ReportViewModel:
    """Build a :class:`ReportViewModel` from disk state."""
    root = Path(root)
    cfg = load_config(root)

    caps_raw = _list_active_capabilities(root)
    capabilities: list[CapabilityView] = []
    for cap in caps_raw:
        cur = read_current(root, cap.frontmatter.capability)
        capabilities.append(_build_capability_view(cap, cur, cfg))

    drafts_raw = _list_draft_capabilities(root)
    drafts: list[CapabilityView] = []
    for cap in drafts_raw:
        cur = read_current(root, cap.frontmatter.capability)
        drafts.append(_build_capability_view(cap, cur, cfg))

    shipped_raw = _list_shipped_capabilities(root)
    shipped: list[CapabilityView] = []
    for cap in shipped_raw:
        cur = read_current(root, cap.frontmatter.capability)
        shipped.append(_build_capability_view(cap, cur, cfg))

    in_flight = _list_in_flight(root)
    by_step: dict[str, int] = {}
    agents: set[str] = set()
    for row in in_flight:
        if not row.alive:
            # Stale claims don't count toward live parallelism. They are still
            # rendered in the table so the operator notices them.
            continue
        by_step[row.step] = by_step.get(row.step, 0) + 1
        agents.add(row.agent_id)
    parallelism = ParallelismView(
        parallel_count=sum(by_step.values()),
        distinct_agents=len(agents),
        by_step=by_step,
    )

    pending_views: list[PendingView] = []
    for path in list_open_pending(root):
        pv = _build_pending_view(path)
        if pv is not None:
            pending_views.append(pv)
    pending_views.sort(key=lambda p: p.filename)

    notifications = _build_notifications(capabilities, pending_views, caps_raw)

    ticks_raw = _list_recent_ticks(root, n=10)
    ticks = [_build_tick_view(tl) for _, tl in ticks_raw]

    shippable = bool(capabilities) and all(
        iv.verdict in _GREEN_VERDICTS
        for cap in capabilities
        for iv in cap.items
    )

    gen_at = _generated_at(root, ticks_raw)
    last_tick_id = ticks_raw[0][1].tick_id if ticks_raw else None

    project_name = root.resolve().name or "i2e"

    return ReportViewModel(
        project_name=project_name,
        generated_at=gen_at,
        generated_at_display=gen_at.strftime("%Y-%m-%d %H:%M:%SZ"),
        last_tick_id=last_tick_id,
        shippable=shippable,
        capabilities=capabilities,
        drafts=drafts,
        shipped=shipped,
        in_flight=in_flight,
        parallelism=parallelism,
        notifications=notifications,
        pending=pending_views,
        ticks=ticks,
        serve_url=_read_serve_url(root),
    )


# ---------- Jinja2 rendering ----------

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _jinja_env() -> jinja2.Environment:
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=jinja2.select_autoescape(["html", "j2", "html.j2"]),
        keep_trailing_newline=True,
    )


def _render_template(template_name: str, vm: ReportViewModel) -> str:
    env = _jinja_env()
    tpl = env.get_template(template_name)
    # Pass the Pydantic models directly so Jinja can use attribute access
    # cleanly (a dict's ``items`` method would otherwise shadow ``cap.items``).
    return tpl.render(
        project_name=vm.project_name,
        generated_at=vm.generated_at,
        generated_at_display=vm.generated_at_display,
        last_tick_id=vm.last_tick_id,
        shippable=vm.shippable,
        capabilities=vm.capabilities,
        drafts=vm.drafts,
        shipped=vm.shipped,
        in_flight=vm.in_flight,
        parallelism=vm.parallelism,
        notifications=vm.notifications,
        pending=vm.pending,
        ticks=vm.ticks,
        serve_url=vm.serve_url,
    )


def render_to_string(root: Path) -> str:
    """Build the view model and render the HTML to a string.

    Pure function over disk state — does not touch ``.i2e/report.html``.
    """
    return _render_template("report.html.j2", build_view_model(Path(root)))


def render_main_to_string(root: Path) -> str:
    """Render only the dynamic ``<main>`` body — used by ``i2e-serve`` AJAX updates.

    Returns the fragment that lives inside ``<main>...</main>``. The client
    swaps this into the live page on SSE ``change`` events to preserve scroll
    position and any open ``<details>`` / ``<textarea>`` input state.
    """
    return _render_template("report_main.html.j2", build_view_model(Path(root)))


def render(root: Path) -> Path:
    """Render and atomically write ``.i2e/report.html``. Returns the path."""
    root = Path(root)
    html = render_to_string(root)
    target = report_path(root)
    atomic_write(target, html)
    return target


__all__ = [
    "CapabilityView",
    "InFlightView",
    "ItemView",
    "NotificationView",
    "ParallelismView",
    "PendingView",
    "ReportViewModel",
    "TickView",
    "build_view_model",
    "render",
    "render_main_to_string",
    "render_to_string",
]
