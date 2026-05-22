"""Console state gatherer — reads ``.i2e/`` into a render-ready view model.

One :func:`gather` call walks intents, evidence, pending, tick logs, and
worktree claims, returning a :class:`ConsoleState` the views render from.
Read-only: never writes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..evidence import read_current
from ..intent import parse_intent
from ..paths import i2e_dir, intents_dir, logs_dir, pending_dir
from ..pending import read_pending
from ..tick_log import TickLog, _read_tick

GROUP_ORDER = ("active", "draft", "shipped", "retired")
_GREEN = frozenset({"pass", "met"})
_FAIL = frozenset({"fail", "unmet"})


@dataclass
class ItemRow:
    """One evidence item or constraint, joined with its current verdict."""

    id: str
    type: str  # case / target / constraint
    provider: str
    query: str
    expect: str
    effort: str
    window: str | None = None
    verdict: str | None = None
    value: str | None = None
    attempts_used: int = 0
    pending: str | None = None


@dataclass
class CapView:
    """A capability intent joined with its evidence verdicts."""

    slug: str
    title: str
    summary: str
    status: str
    watcher: str
    version: int
    created: str
    updated: str
    depends_on: list[str]
    touches: list[str]
    spec: str | None
    spec_section: str | None
    evidence: list[ItemRow]
    constraints: list[ItemRow]
    source: str
    started: bool = False

    @property
    def items(self) -> list[ItemRow]:
        return [*self.evidence, *self.constraints]

    @property
    def counts(self) -> dict[str, int]:
        c = {"pass": 0, "fail": 0, "trending": 0, "awaiting": 0, "none": 0}
        for it in self.items:
            v = it.verdict
            if v in _GREEN:
                c["pass"] += 1
            elif v in _FAIL:
                c["fail"] += 1
            elif v == "trending":
                c["trending"] += 1
            elif v == "awaiting_human":
                c["awaiting"] += 1
            else:
                c["none"] += 1
        return c

    @property
    def shippable(self) -> bool:
        return bool(self.items) and all(it.verdict in _GREEN for it in self.items)

    @property
    def health(self) -> str:
        """Dominant verdict key — drives dot / segment colour."""
        c = self.counts
        if c["fail"]:
            return "fail"
        if c["awaiting"]:
            return "awaiting_human"
        if c["trending"]:
            return "trending"
        if self.shippable:
            return "pass"
        if self.status == "shipped":
            return "shipped"
        return "nodata"


@dataclass
class PendingView:
    """An open pending file joined with its watcher."""

    file: str
    kind: str
    capability: str
    item_id: str
    ask: str
    expect: str | None
    observed: str | None
    watcher: str
    asked_at: datetime | None
    status: str
    verdict_options: list[str]
    attempts: list = field(default_factory=list)


@dataclass
class ConsoleState:
    capabilities: list[CapView]
    pendings: list[PendingView]
    workers: list[dict]
    ticks: list[TickLog]

    def cap(self, slug: str) -> CapView | None:
        for c in self.capabilities:
            if c.slug == slug:
                return c
        return None

    def by_status(self, status: str) -> list[CapView]:
        return [c for c in self.capabilities if c.status == status]

    def status_counts(self) -> dict[str, int]:
        return {s: len(self.by_status(s)) for s in GROUP_ORDER}

    def pendings_for(self, slug: str) -> list[PendingView]:
        return [p for p in self.pendings if p.capability == slug]

    def workers_for(self, slug: str) -> list[dict]:
        return [w for w in self.workers if w.get("capability") == slug]


def _title_summary(description: str, slug: str) -> tuple[str, str]:
    text = (description or "").strip()
    if not text:
        return slug, ""
    lines = text.splitlines()
    title = lines[0].lstrip("#").strip() or slug
    summary = "\n".join(lines[1:]).strip()
    return title, summary


def _gather_capabilities(root: Path) -> list[CapView]:
    base = intents_dir(root)
    out: list[CapView] = []
    if not base.exists():
        return out
    for p in sorted(base.glob("*.md")):
        try:
            cap = parse_intent(p)
        except Exception:
            continue
        fm = cap.frontmatter
        cur = read_current(root, fm.capability)
        verdicts = cur.items if cur else {}

        def _row(item, kind: str) -> ItemRow:
            v = verdicts.get(item.id)
            return ItemRow(
                id=item.id,
                type=kind,
                provider=item.provider,
                query=item.query,
                expect=item.expect,
                effort=getattr(item, "effort", "medium"),
                window=getattr(item, "window", None),
                verdict=v.verdict if v else None,
                value=v.value if v else None,
                attempts_used=v.attempts_used if v else 0,
                pending=v.pending if v else None,
            )

        title, summary = _title_summary(cap.description, fm.capability)
        out.append(
            CapView(
                slug=fm.capability,
                title=title,
                summary=summary,
                status=fm.status,
                watcher=fm.watcher,
                version=fm.version,
                created=str(fm.created),
                updated=str(fm.updated),
                depends_on=list(fm.depends_on),
                touches=list(fm.touches),
                spec=fm.spec,
                spec_section=fm.spec_section,
                evidence=[_row(it, it.type) for it in cap.evidence],
                constraints=[_row(it, "constraint") for it in cap.constraints],
                source=p.read_text(encoding="utf-8"),
                started=cur is not None,
            )
        )
    return out


def _gather_pendings(root: Path, watcher_of: dict[str, str]) -> list[PendingView]:
    base = pending_dir(root)
    out: list[PendingView] = []
    if not base.exists():
        return out
    for p in sorted(base.glob("*.yaml")):
        try:
            pf = read_pending(p)
        except Exception:
            continue
        if pf.status != "open":
            continue
        out.append(
            PendingView(
                file=p.name,
                kind=pf.kind,
                capability=pf.capability,
                item_id=pf.item_id,
                ask=pf.ask,
                expect=pf.expect,
                observed=pf.observed,
                watcher=watcher_of.get(pf.capability, "@me"),
                asked_at=pf.asked_at,
                status=pf.status,
                verdict_options=pf.verdict_options or ["yes", "no", "partial"],
                attempts=list(pf.attempts or []),
            )
        )
    return out


def _gather_workers(root: Path) -> list[dict]:
    base = i2e_dir(root) / "worktrees"
    out: list[dict] = []
    if not base.exists():
        return out
    for slug_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        claim = slug_dir / "claim.json"
        if not claim.exists():
            continue
        try:
            data = json.loads(claim.read_text(encoding="utf-8"))
        except Exception:
            continue
        log = slug_dir / "log"
        tail: list[str] = []
        if log.exists():
            try:
                tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]
            except Exception:
                tail = []
        data["_log_tail"] = tail
        out.append(data)
    return out


def _gather_ticks(root: Path, limit: int | None = None) -> list[TickLog]:
    base = logs_dir(root)
    if not base.exists():
        return []
    cands = sorted(
        (p for p in base.glob("*-tick.yaml") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    out: list[TickLog] = []
    for p in cands:
        tl = _read_tick(p)
        if tl is not None:
            out.append(tl)
        if limit is not None and len(out) >= limit:
            break
    return out


def tick_phase(tick: TickLog) -> str:
    """Best-effort IDEA phase for a tick, derived from its action strings."""
    blob = " ".join(tick.actions).lower()
    if "develop" in blob:
        return "develop"
    if "evidence" in blob:
        return "evidence"
    if "adapt" in blob or "escalat" in blob:
        return "adapt"
    return "intent"


def gather(root: Path) -> ConsoleState:
    """Read the whole ``.i2e/`` tree into a :class:`ConsoleState`."""
    root = Path(root)
    caps = _gather_capabilities(root)
    watcher_of = {c.slug: c.watcher for c in caps}
    return ConsoleState(
        capabilities=caps,
        pendings=_gather_pendings(root, watcher_of),
        workers=_gather_workers(root),
        ticks=_gather_ticks(root),
    )
