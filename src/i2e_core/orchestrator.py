"""Orchestrator — the deterministic core of the `i2e` skill.

`i2e` is the front-door skill. It runs a preflight scan and advances the
project by exactly one step using the IDEA loop's 5-branch decision tree
(spec §6.1). Each non-empty tick auto-invokes `i2e_core.report.render` so
``.i2e/report.html`` stays fresh.

Public entry points
-------------------
- :func:`preflight` — re-runs forced-evidence + effort-tier validation across
  every ``status: active`` intent. Returns a :class:`PreflightResult`.
- :func:`decide` — evaluates the 5-branch decision tree in strict order and
  returns the chosen :class:`Action`.
- :func:`tick` — preflight + decide + execute + log + report. Returns a
  :class:`TickResult`.
- :func:`parse_window` — ``"5m"`` / ``"7d"`` / ``"2w"`` ⇒ ``timedelta``.

Action grammar (the tagged union returned by :func:`decide`)
------------------------------------------------------------
- :class:`ApplyResolutions` — at least one ``status: resolved`` pending file
- :class:`DevelopAndEvidence` — an active intent has no current.yaml, or
  ``current.intent_version`` is older than ``frontmatter.version``
- :class:`AdaptThenRetry` — ``adapt.plan(...).retries`` is non-empty for the
  capability
- :class:`ReEvaluateItem` — a target/case has ``last_observed`` older than
  ``item.window`` and verdict in ``{met, unmet, trending}``
- :class:`Shippable` — nothing to do

Determinism: capabilities are walked in alphabetical order, so the same
project state always produces the same action.

CLI
---
``python -m i2e_core.orchestrator`` runs one tick. Exit codes:

- 0 — tick completed (Shippable or not)
- 1 — preflight failed
- 2 — an unexpected exception escaped
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from . import adapt, evidence_runner
from .config import load_config
from .deps import build_graph, find_cycle, find_unknown_refs, ready_slugs
from .develop import scoped_capabilities
from .evidence import read_current
from .init import init_project
from .intent import parse_intent
from .paths import i2e_dir, intents_dir
from .pending import list_resolved_pending
from .provider.discovery import installed_provider_names
from .report import render
from .report.links import deep_link
from .runid import new_run_id
from .tick_log import TickLog, write_tick
from .validator import ValidationError, validate_capability_with_config


# ---------- Window parsing ----------

_WINDOW_RE = re.compile(r"^\s*(\d+)\s*([mhdw])\s*$")
_WINDOW_UNITS: dict[str, str] = {
    "m": "minutes",
    "h": "hours",
    "d": "days",
    "w": "weeks",
}


def parse_window(s: str) -> timedelta:
    """Parse a window string like ``"5m"``, ``"2h"``, ``"7d"``, ``"4w"``.

    Raises :class:`ValueError` on any other shape (including empty strings,
    bare numbers, or unsupported units like ``"30s"``).
    """
    if not isinstance(s, str) or not s:
        raise ValueError(f"window must be a non-empty string, got {s!r}")
    m = _WINDOW_RE.match(s)
    if not m:
        raise ValueError(
            f"window {s!r} does not match Nm|Nh|Nd|Nw "
            "(e.g. '5m', '2h', '7d', '4w')"
        )
    n = int(m.group(1))
    unit = _WINDOW_UNITS[m.group(2)]
    return timedelta(**{unit: n})


# ---------- Preflight ----------


class PreflightResult(BaseModel):
    """Aggregated preflight outcome."""

    model_config = ConfigDict(extra="forbid")

    valid: bool
    errors: dict[str, list[str]] = Field(default_factory=dict)


class PreflightFailed(Exception):
    """Raised by :func:`tick` when preflight reports any invalid intent."""

    def __init__(self, result: PreflightResult):
        self.result = result
        if not result.errors:
            super().__init__("preflight failed (no specific errors recorded)")
            return
        lines = ["preflight failed:"]
        for cap, errs in result.errors.items():
            lines.append(f"  [{cap}]")
            for e in errs:
                lines.append(f"    - {e}")
        super().__init__("\n".join(lines))


def _preflight_cache_path(root: Path) -> Path:
    return i2e_dir(Path(root)) / ".preflight_cache.json"


def _intents_mtime_hash(root: Path) -> str:
    """Stable hash of ``{intent_name: mtime_ns}`` over ``.i2e/intents/*.md``.

    Used to detect when no intent file has changed since the last green
    preflight; in that case we can safely skip re-parsing every intent.
    """
    base = intents_dir(Path(root))
    if not base.exists():
        return "no-intents-dir"
    parts: list[str] = []
    for p in sorted(base.glob("*.md")):
        try:
            mtime_ns = p.stat().st_mtime_ns
        except OSError:
            continue
        parts.append(f"{p.name}:{mtime_ns}")
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _read_preflight_cache_hash(root: Path) -> str | None:
    p = _preflight_cache_path(root)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    h = data.get("hash") if isinstance(data, dict) else None
    return h if isinstance(h, str) else None


def _write_preflight_cache(root: Path, hash_val: str) -> None:
    p = _preflight_cache_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"hash": hash_val}), encoding="utf-8")


def _invalidate_preflight_cache(root: Path) -> None:
    p = _preflight_cache_path(root)
    if p.exists():
        try:
            p.unlink()
        except OSError:
            pass


def preflight(root: Path) -> PreflightResult:
    """Re-run forced-evidence + effort-tier validation over every active intent.

    Walks ``.i2e/intents/*.md`` in alphabetical order, parses each, and runs
    :func:`validate_capability_with_config` against the loaded config and the
    set of currently installed providers. Errors are aggregated per
    capability so the operator sees every problem at once instead of one at
    a time.

    Drafts and retired intents are skipped — drafts are by definition
    work-in-progress, retired intents are frozen.

    A green result is cached in ``.i2e/.preflight_cache.json`` keyed by the
    hash of every intent file's mtime. On the next tick, if no intent file
    has been touched, the cache short-circuits the parse+validate pass.
    Any mtime change (edit, add, remove) invalidates the cache.
    """
    root = Path(root)

    # Fast path: cached green result still applies.
    current_hash = _intents_mtime_hash(root)
    cached_hash = _read_preflight_cache_hash(root)
    if cached_hash is not None and cached_hash == current_hash:
        return PreflightResult(valid=True, errors={})

    cfg = load_config(root)
    providers = installed_provider_names()
    base = intents_dir(root)
    errors: dict[str, list[str]] = {}

    if not base.exists():
        _write_preflight_cache(root, current_hash)
        return PreflightResult(valid=True, errors={})

    for path in sorted(base.glob("*.md")):
        try:
            cap = parse_intent(path)
        except Exception as e:  # parsing failure is itself a preflight error
            errors.setdefault(path.stem, []).append(f"parse failed: {e}")
            continue
        if cap.frontmatter.status != "active":
            continue
        try:
            validate_capability_with_config(cap, cfg, providers)
        except ValidationError as ve:
            errors.setdefault(cap.frontmatter.capability, []).extend(ve.errors)

    # depends_on graph: unknown refs first (so a cycle through a missing node
    # is reported as "unknown ref" rather than masquerading as a cycle).
    graph = build_graph(root)
    for slug, missing in find_unknown_refs(graph):
        errors.setdefault(slug, []).append(
            f"depends_on references unknown capability {missing!r}"
        )
    if not any(
        "depends_on references unknown" in m
        for errs in errors.values()
        for m in errs
    ):
        cycle = find_cycle(graph)
        if cycle is not None:
            chain = " -> ".join(cycle)
            for slug in {s for s in cycle}:
                errors.setdefault(slug, []).append(
                    f"depends_on cycle: {chain}"
                )

    if errors:
        _invalidate_preflight_cache(root)
    else:
        _write_preflight_cache(root, current_hash)

    return PreflightResult(valid=not errors, errors=errors)


# ---------- Action tagged union ----------


class ApplyResolutions(BaseModel):
    """Branch 1: at least one resolved pending file is ready to apply."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["apply_resolutions"] = "apply_resolutions"


class DevelopAndEvidence(BaseModel):
    """Branch 2: an active capability needs develop (no current, or version bumped)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["develop"] = "develop"
    capability: str


class AdaptThenRetry(BaseModel):
    """Branch 3: a capability has retry-eligible items (budget remains)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["adapt_retry"] = "adapt_retry"
    capability: str


class ReEvaluateItem(BaseModel):
    """Branch 4: a single item's window has elapsed since last_observed."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["reevaluate"] = "reevaluate"
    capability: str
    item_id: str


class Shippable(BaseModel):
    """Branch 5: nothing to do."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["shippable"] = "shippable"


Action = Union[
    ApplyResolutions,
    DevelopAndEvidence,
    AdaptThenRetry,
    ReEvaluateItem,
    Shippable,
]


# ---------- decide ----------


def _active_capabilities(root: Path) -> list[str]:
    """Return slugs of all ``status: active`` intents, alphabetical."""
    base = intents_dir(Path(root))
    if not base.exists():
        return []
    out: list[str] = []
    for path in sorted(base.glob("*.md")):
        try:
            cap = parse_intent(path)
        except Exception:
            continue
        if cap.frontmatter.status == "active":
            out.append(cap.frontmatter.capability)
    return sorted(out)


def _branch4_capabilities(root: Path) -> list[str]:
    """Branch 4 candidates: active *and* shipped intents, alphabetical.

    Shipped capabilities still re-evaluate target windows (spec §6.1) —
    a stale target on a shipped capability can demote it back to active.
    """
    base = intents_dir(Path(root))
    if not base.exists():
        return []
    out: list[str] = []
    for path in sorted(base.glob("*.md")):
        try:
            cap = parse_intent(path)
        except Exception:
            continue
        if cap.frontmatter.status in ("active", "shipped"):
            out.append(cap.frontmatter.capability)
    return sorted(out)


def _item_window_for(root: Path, capability: str, item_id: str) -> str | None:
    """Look up the ``window:`` field for an item in the intent file.

    Returns ``None`` if the item has no window (constraints never do; cases
    rarely do) or if the item has been retired between runs.
    """
    base = intents_dir(Path(root))
    path = base / f"{capability}.md"
    if not path.exists():
        return None
    try:
        cap = parse_intent(path)
    except Exception:
        return None
    for ev in cap.evidence:
        if ev.id == item_id:
            return ev.window
    # Constraints have no window field by design.
    return None


_WINDOW_VERDICTS = frozenset({"met", "unmet", "trending"})


def decide(root: Path) -> Action:
    """Walk the 5-branch decision tree in order; return the first match.

    See module docstring for the action grammar. Strict first-match-wins
    semantics — branch 1 always beats branch 2, etc.
    """
    root = Path(root)

    # Fast-path short-circuit: if there are no active capabilities, no
    # resolved pendings, AND no shipped capabilities, none of the five
    # branches can fire — every one of them is gated on one of those.
    # Shipped capabilities can still fire branch 4 (target window
    # re-evaluation) so they must keep decide() alive.
    resolved = list_resolved_pending(root)
    active = _active_capabilities(root)
    shipped = [
        s for s in _branch4_capabilities(root) if s not in active
    ]
    if not resolved and not active and not shipped:
        return Shippable()

    # Branch 1: resolved pending files awaiting application.
    if resolved:
        return ApplyResolutions()

    # Branch 2: an active capability needs develop (new or version-bumped).
    # depends_on respects ordering: a child never fires while a parent still
    # needs develop. Among the ready set, alphabetical breaks ties (spec §6.1).
    scoped = scoped_capabilities(root)
    if scoped:
        scoped_slugs = {c.frontmatter.capability for c in scoped}
        graph = build_graph(root)
        ready = ready_slugs(graph, scoped_slugs)
        # ready is always non-empty when scoped is non-empty: preflight rejects
        # cycles, so the DAG over scoped has at least one source.
        if ready:
            return DevelopAndEvidence(capability=sorted(ready)[0])
        # Defensive fallback: preflight should have caught any cycle, but if
        # one slips through, falling back to alphabetical keeps the loop alive.
        return DevelopAndEvidence(capability=sorted(scoped_slugs)[0])

    # Branch 3: a capability has retry-eligible items.
    for cap_slug in active:
        try:
            pl = adapt.plan(root, cap_slug)
        except Exception:
            continue
        if pl.retries:
            return AdaptThenRetry(capability=cap_slug)

    # Branch 4: a window has elapsed for some item.
    # Shipped capabilities still re-evaluate target windows; only branches
    # 1-3 skip shipped (spec §6.1, intent-shipped-status).
    now = datetime.now(timezone.utc)
    for cap_slug in _branch4_capabilities(root):
        cur = read_current(root, cap_slug)
        if cur is None:
            continue
        for item_id in sorted(cur.items.keys()):
            verdict = cur.items[item_id]
            if verdict.verdict not in _WINDOW_VERDICTS:
                continue
            if verdict.last_observed is None:
                continue
            window_str = _item_window_for(root, cap_slug, item_id)
            if not window_str:
                continue
            try:
                window = parse_window(window_str)
            except ValueError:
                continue
            # Normalise last_observed to UTC if it's naive.
            last = verdict.last_observed
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if now - last > window:
                return ReEvaluateItem(capability=cap_slug, item_id=item_id)

    # Branch 5: nothing to do.
    return Shippable()


# ---------- tick ----------


class TickResult(BaseModel):
    """The orchestrator's per-tick contract.

    ``actions_log`` is empty iff the tick was a no-op (Shippable). In that
    case ``report_path`` is also ``None`` and no tick log file is written.
    """

    model_config = ConfigDict(extra="forbid")

    tick_id: str
    action: Action
    actions_log: list[str] = Field(default_factory=list)
    report_path: Path | None = None
    report_link: str | None = None
    shippable: bool


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# Narrow status-write carve-out for the orchestrator (spec §6.1,
# intent-shipped-status). Only the auto-promote/auto-demote paths in
# :func:`tick` may call these — every other status edit goes through
# ``i2e-intent`` / ``intent_authoring.set_intent_status`` directly.

_SHIPPED_GREEN_VERDICTS = frozenset({"pass", "met"})


def _all_green(root: Path, capability: str) -> bool:
    """True iff every item in ``current.yaml`` has a green verdict.

    Returns ``False`` when no ``current.yaml`` exists or the file is
    empty — there is no evidence to call green.
    """
    cur = read_current(root, capability)
    if cur is None or not cur.items:
        return False
    return all(
        iv.verdict in _SHIPPED_GREEN_VERDICTS for iv in cur.items.values()
    )


def _orchestrator_promote_to_shipped(root: Path, capability: str) -> bool:
    """Orchestrator carve-out: flip ``active`` → ``shipped``.

    Returns True iff the status actually changed. No-op if the intent file
    is missing or the capability is not currently ``active``.
    """
    # Local import to avoid a top-level cycle: intent_authoring imports
    # validation helpers that pull in this module's siblings.
    from .intent_authoring import set_intent_status

    path = intents_dir(Path(root)) / f"{capability}.md"
    if not path.exists():
        return False
    try:
        cap = parse_intent(path)
    except Exception:
        return False
    if cap.frontmatter.status != "active":
        return False
    set_intent_status(root, capability, "shipped")
    return True


def _orchestrator_demote_to_active(root: Path, capability: str) -> bool:
    """Orchestrator carve-out: flip ``shipped`` → ``active``.

    Returns True iff the status actually changed.
    """
    from .intent_authoring import set_intent_status

    path = intents_dir(Path(root)) / f"{capability}.md"
    if not path.exists():
        return False
    try:
        cap = parse_intent(path)
    except Exception:
        return False
    if cap.frontmatter.status != "shipped":
        return False
    set_intent_status(root, capability, "active")
    return True


_DEMOTE_VERDICTS = frozenset({"fail", "unmet", "trending"})


def _maybe_demote_after_reevaluate(
    root: Path, capability: str, item_id: str
) -> bool:
    """Demote ``capability`` from shipped → active iff the re-evaluated item
    flipped to ``fail``/``unmet``/``trending``.

    Returns True iff a status flip happened.
    """
    cur = read_current(root, capability)
    if cur is None:
        return False
    iv = cur.items.get(item_id)
    if iv is None:
        return False
    if iv.verdict not in _DEMOTE_VERDICTS:
        return False
    return _orchestrator_demote_to_active(root, capability)


def tick(root: Path) -> TickResult:
    """Run one orchestrator tick. Raises :class:`PreflightFailed` on bad state.

    See the module docstring for the full flow.
    """
    root = Path(root)

    # First-run scaffold: ensure the .i2e/ layout and helper scripts exist
    # before anything reads or writes beneath it. Idempotent — a no-op on
    # every tick after the first. Deliberate boundary carve-out: the
    # orchestrator otherwise writes only .i2e/logs/** and report.html
    # (see CLAUDE.md boundary table).
    init_project(root)

    pre = preflight(root)
    if not pre.valid:
        raise PreflightFailed(pre)

    tick_id = new_run_id()
    action = decide(root)
    actions_log: list[str] = []

    if isinstance(action, ApplyResolutions):
        applied = adapt.apply_resolutions(root)
        for a in applied:
            actions_log.append(
                f"applied_resolution: {a.capability} / {a.item_id}"
            )

    elif isinstance(action, DevelopAndEvidence):
        # The develop step is LLM-driven; the orchestrator only records the
        # action string. The next tick will converge once develop completes
        # (or the evidence runner picks up the new src/ layout below).
        actions_log.append(
            f"ran_develop: {action.capability} (LLM-driven; subprocess hook deferred)"
        )
        try:
            summary = evidence_runner.run(root, action.capability)
            actions_log.append(
                f"ran_evidence: {action.capability} ({summary.compact()})"
            )
        except Exception as e:
            # Evidence-runner failure surfaces in the action log but does
            # not crash the tick — the next tick will retry.
            actions_log.append(
                f"ran_evidence: {action.capability} (failed: {e})"
            )
        # Auto-promote active → shipped when every verdict is green
        # (intent-shipped-status, §6.1).
        if _all_green(root, action.capability) and _orchestrator_promote_to_shipped(
            root, action.capability
        ):
            actions_log.append(
                f"promoted_to_shipped: {action.capability}"
            )

    elif isinstance(action, AdaptThenRetry):
        pl = adapt.plan(root, action.capability)
        actions_log.append(
            f"ran_adapt: {action.capability} "
            f"(retries={len(pl.retries)}, escalations={len(pl.escalations)})"
        )
        for ib in pl.escalations:
            try:
                adapt.escalate(root, action.capability, ib.item_id)
            except FileExistsError:
                # Pending file already on disk — adapt.has_open_escalation
                # should have filtered it, but be defensive.
                continue
            except Exception:
                # Best-effort batch: an escalation failure on one item must
                # not block the others.
                continue

    elif isinstance(action, ReEvaluateItem):
        try:
            summary = evidence_runner.run(
                root, action.capability, only_items=[action.item_id]
            )
            actions_log.append(
                f"ran_evidence: {action.capability} ({summary.compact()})"
            )
        except Exception as e:
            actions_log.append(
                f"ran_evidence: {action.capability} (failed: {e})"
            )
        # Auto-demote shipped → active if the re-evaluated item regressed
        # (intent-shipped-status, §6.1).
        if _maybe_demote_after_reevaluate(
            root, action.capability, action.item_id
        ):
            actions_log.append(
                f"demoted_to_active: {action.capability}"
            )

    # Shippable → leave actions_log empty.

    # End-of-tick sweep: any active capability whose current.yaml is
    # all-green gets auto-promoted to shipped, even if the tick's primary
    # action did not touch it (e.g. AdaptThenRetry on capability X with a
    # separate capability Y silently going green). The carve-out remains
    # narrow — only active → shipped, never any other transition.
    for cap_slug in _active_capabilities(root):
        if _all_green(root, cap_slug) and _orchestrator_promote_to_shipped(
            root, cap_slug
        ):
            actions_log.append(f"promoted_to_shipped: {cap_slug}")

    # Tick log: write only if something happened (spec §9).
    if actions_log:
        write_tick(
            root,
            TickLog(
                tick_id=tick_id,
                ran_at=_now_utc(),
                actions=list(actions_log),
            ),
        )

    # Report: refresh on any non-empty tick.
    report_path: Path | None = None
    report_link: str | None = None
    if actions_log:
        report_path = render(root)
        focus = _focus_for_action(action, root)
        report_link = deep_link(root, focus)

    return TickResult(
        tick_id=tick_id,
        action=action,
        actions_log=actions_log,
        report_path=report_path,
        report_link=report_link,
        shippable=isinstance(action, Shippable),
    )


def _focus_for_action(action: Action, root: Path | None = None) -> str:
    """Return a deep-link fragment matching the action's focus capability.

    When ``root`` is provided we read the current intent status and pick
    the right anchor — a capability auto-promoted to ``shipped`` during
    this tick lives in the Shipped section (``#shipped/<slug>``) rather
    than the active card list (``#cap/<slug>``).
    """
    def _cap_anchor(slug: str) -> str:
        if root is None:
            return f"#cap/{slug}"
        path = intents_dir(Path(root)) / f"{slug}.md"
        if path.exists():
            try:
                status = parse_intent(path).frontmatter.status
                if status == "shipped":
                    return f"#shipped/{slug}"
            except Exception:
                pass
        return f"#cap/{slug}"

    if isinstance(action, DevelopAndEvidence):
        return _cap_anchor(action.capability)
    if isinstance(action, AdaptThenRetry):
        return _cap_anchor(action.capability)
    if isinstance(action, ReEvaluateItem):
        return f"#item/{action.capability}/{action.item_id}"
    # ApplyResolutions / Shippable don't have a single focus — link to top.
    return ""


# ---------- CLI ----------


def _tick_to_jsonable(tr: TickResult) -> dict:
    """Render a :class:`TickResult` in a JSON-safe shape."""
    data = tr.model_dump(mode="json")
    # Path objects are stringified by mode='json', but be explicit for clarity.
    if tr.report_path is not None:
        data["report_path"] = str(tr.report_path)
    return data


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m i2e_core.orchestrator",
        description="Run one orchestrator tick.",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Project root (containing .i2e/). Defaults to cwd.",
    )
    args = parser.parse_args(argv)

    try:
        result = tick(Path(args.root))
    except PreflightFailed as pf:
        print(str(pf), file=sys.stderr)
        return 1
    except Exception:  # pragma: no cover - tested via subprocess
        traceback.print_exc()
        return 2

    print(json.dumps(_tick_to_jsonable(result), sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - thin CLI shim
    raise SystemExit(_main(sys.argv[1:]))


__all__ = [
    "Action",
    "AdaptThenRetry",
    "ApplyResolutions",
    "DevelopAndEvidence",
    "PreflightFailed",
    "PreflightResult",
    "ReEvaluateItem",
    "Shippable",
    "TickResult",
    "decide",
    "parse_window",
    "preflight",
    "tick",
]
