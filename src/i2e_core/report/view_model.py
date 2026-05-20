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
from ..tick_log import TickLog, _read_tick


# ---------- Pydantic view models ----------


_GREEN_VERDICTS = frozenset({"pass", "met"})

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


def _build_item_view(
    item_id: str,
    item_type: str,
    provider: str,
    effort: str,
    cfg: I2EConfig,
    verdict: ItemVerdict | None,
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
    spec_items: list[tuple[str, str, str, str]] = []  # (id, type, provider, effort)
    for ev in cap.evidence:
        spec_items.append((ev.id, ev.type, ev.provider, ev.effort))
    for cn in cap.constraints:
        spec_items.append((cn.id, "constraint", cn.provider, cn.effort))
    spec_items.sort(key=lambda t: t[0])

    for item_id, item_type, provider, effort in spec_items:
        verdict = current_items.get(item_id)
        items.append(
            _build_item_view(item_id, item_type, provider, effort, cfg, verdict)
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


def _list_recent_ticks(root: Path, n: int = 10) -> list[tuple[Path, TickLog]]:
    base = logs_dir(Path(root))
    if not base.exists():
        return []
    candidates = sorted(
        (p for p in base.glob("*-tick.yaml") if p.is_file()),
        key=lambda p: p.name,
        reverse=True,
    )
    out: list[tuple[Path, TickLog]] = []
    for p in candidates:
        tl = _read_tick(p)
        if tl is not None:
            out.append((p, tl))
        if len(out) >= n:
            break
    return out


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

    pending_views: list[PendingView] = []
    for path in list_open_pending(root):
        pv = _build_pending_view(path)
        if pv is not None:
            pending_views.append(pv)
    pending_views.sort(key=lambda p: p.filename)

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


def render_to_string(root: Path) -> str:
    """Build the view model and render the HTML to a string.

    Pure function over disk state — does not touch ``.i2e/report.html``.
    """
    vm = build_view_model(Path(root))
    env = _jinja_env()
    tpl = env.get_template("report.html.j2")
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
        pending=vm.pending,
        ticks=vm.ticks,
        serve_url=vm.serve_url,
    )


def render(root: Path) -> Path:
    """Render and atomically write ``.i2e/report.html``. Returns the path."""
    root = Path(root)
    html = render_to_string(root)
    target = report_path(root)
    atomic_write(target, html)
    return target


__all__ = [
    "CapabilityView",
    "ItemView",
    "PendingView",
    "ReportViewModel",
    "TickView",
    "build_view_model",
    "render",
    "render_to_string",
]
