"""Console sidebar — dark rail with project nav + grouped intent list.

Renders the full ``<aside class="sidebar">`` element. Grouped-by-status is
the default treatment; section headers (``data-group``) are stable so the
SSE refresh can target them. Read-only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from .. import ui
from ..state import GROUP_ORDER, ConsoleState, gather

SidebarMode = Literal["grouped", "flat", "tree"]

_NAV = (
    ("dashboard", "Dashboard", "/"),
    ("pending", "Pending", "/pending"),
    ("workers", "Workers", "/workers"),
    ("logs", "Logs", "/logs"),
    ("specs", "Specs", "/specs"),
)


def _intent_dot(cap) -> str:
    """Status/health dot kind for a sidebar row."""
    if cap.status == "shipped":
        return "shipped"
    if cap.status == "retired":
        return "retired"
    health = cap.health
    if health in ("fail", "awaiting_human", "trending", "pass"):
        return {"pass": "pass"}.get(health, health)
    return "draft"


def _row(cap, selected_slug: str | None, pend_count: int, inflight: bool) -> str:
    cls = "intent-row"
    if cap.status == "retired":
        cls += " retired"
    if cap.slug == selected_slug:
        cls += " active"
    marker = (
        '<span class="pulse" style="width:8px;height:8px"></span>'
        if inflight
        else ui.dot(_intent_dot(cap))
    )
    pend = (
        f'<span class="ir-pend">{pend_count}</span>' if pend_count else ""
    )
    return (
        f'<a class="{cls}" data-slug="{ui.esc(cap.slug)}" '
        f'data-status="{ui.esc(cap.status)}" href="/intent/{ui.esc(cap.slug)}">'
        f"{marker}"
        f'<span class="ir-slug">{ui.esc(cap.slug)}</span>{pend}</a>'
    )


def _matches(cap, q: str | None) -> bool:
    if not q:
        return True
    needle = q.strip().lower()
    return (
        needle in cap.slug.lower()
        or needle in cap.title.lower()
        or needle in (cap.watcher or "").lower()
    )


def render_sidebar(
    root: Path,
    mode: SidebarMode = "grouped",
    *,
    active: str | None = None,
    selected_slug: str | None = None,
    state: ConsoleState | None = None,
    nav_path: str = "/",
    flt: str | None = None,
    q: str | None = None,
) -> str:
    if state is None:
        state = gather(Path(root))

    counts = state.status_counts()
    total = len(state.capabilities)
    open_pendings = len(state.pendings)
    workers = len(state.workers)
    pend_by_cap: dict[str, int] = {}
    for p in state.pendings:
        pend_by_cap[p.capability] = pend_by_cap.get(p.capability, 0) + 1
    inflight = {w.get("capability") for w in state.workers}

    # Nav rail
    nav_items = []
    for key, label, href in _NAV:
        badge = ""
        if key == "pending" and open_pendings:
            badge = f'<span class="nav-badge">{open_pendings}</span>'
        elif key == "workers" and workers:
            badge = f'<span class="nav-badge">{workers}</span>'
        cls = "nav-item active" if active == key else "nav-item"
        nav_items.append(
            f'<a class="{cls}" href="{href}">'
            f'<span class="ico">{ui.icon(key)}</span>'
            f'<span class="label">{ui.esc(label)}</span>{badge}</a>'
        )

    # Filter chips
    qs = f"&q={ui.esc(q)}" if q else ""
    chips = []
    for label, key in (
        ("Active", "active"),
        ("Drafts", "draft"),
        ("Shipped", "shipped"),
        ("Retired", "retired"),
        ("All", "all"),
    ):
        n = total if key == "all" else counts.get(key, 0)
        cls = "filter-chip active" if (flt or "all") == key else "filter-chip"
        chips.append(
            f'<a class="{cls}" href="/?flt={key}{qs}">'
            f'<span>{label}</span><span class="fc-count">{n}</span></a>'
        )
    filter_html = (
        f'<div class="filter-row">{"".join(chips[:3])}</div>'
        f'<div class="filter-row">{"".join(chips[3:])}</div>'
    )

    # Intent list — grouped (default), flat, or tree-by-spec.
    def _row_for(cap) -> str:
        return _row(
            cap, selected_slug, pend_by_cap.get(cap.slug, 0), cap.slug in inflight
        )

    visible_filter = flt or "all"
    selected = sorted(
        (
            c
            for c in state.capabilities
            if _matches(c, q) and visible_filter in ("all", c.status)
        ),
        key=lambda c: c.slug,
    )
    shown = len(selected)

    if mode == "flat":
        list_html = (
            '<section class="group" data-group="flat">'
            + "".join(_row_for(c) for c in selected)
            + "</section>"
        )
    elif mode == "tree":
        by_spec: dict[str, list] = {}
        for c in selected:
            by_spec.setdefault(c.spec or "(no spec)", []).append(c)
        chunks = []
        for spec in sorted(by_spec):
            members = by_spec[spec]
            chunks.append(
                f'<section class="group" data-group="{ui.esc(spec)}">'
                f'<div class="sb-group-head">{ui.esc(spec)} &nbsp;·&nbsp; '
                f'{len(members)}</div>'
                + "".join(_row_for(c) for c in members)
                + "</section>"
            )
        list_html = "".join(chunks)
    else:  # grouped — one section per status, all four always emitted.
        sections = []
        for status in GROUP_ORDER:
            members = [c for c in selected if c.status == status]
            head = (
                f'<div class="sb-group-head">{status} &nbsp;·&nbsp; '
                f"{len(members)}</div>"
                if members
                else ""
            )
            sections.append(
                f'<section class="group" data-group="{status}">'
                + head
                + "".join(_row_for(c) for c in members)
                + "</section>"
            )
        list_html = "".join(sections)
    if shown == 0:
        list_html += '<div class="sb-empty">no intents match</div>'

    return f"""<aside class="sidebar" id="sidebar" data-mode="{mode}">
  <div class="wordmark"><span class="logo">i2e</span><span class="tag">console</span></div>
  <div class="project-chip">
    <span class="pico">{ui.esc((Path(root).resolve().name[:1] or 'i').upper())}</span>
    <div style="flex:1;min-width:0">
      <div class="pname">{ui.esc(Path(root).resolve().name or 'project')}</div>
      <div class="ppath">.i2e</div>
    </div>
  </div>
  <nav class="nav">{"".join(nav_items)}</nav>
  <div class="sb-divider"></div>
  <div>
    <div class="intents-head">
      <span class="ttl">Intents</span>
      <span class="cnt">{shown} of {total}</span>
    </div>
    <form method="get" action="/">
      {f'<input type="hidden" name="flt" value="{ui.esc(flt)}">' if flt else ''}
      <input class="sb-search" type="text" name="q" value="{ui.esc(q or '')}" placeholder="search slug / watcher">
    </form>
    {filter_html}
    <div class="intent-list">{list_html}</div>
  </div>
  <div class="sb-foot">
    <div class="serve-line">
      <span class="pulse green" style="width:6px;height:6px"></span>
      <span class="mono">i2e-serve · 127.0.0.1</span>
    </div>
  </div>
</aside>"""
