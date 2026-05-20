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
from .develop import scoped_capabilities
from .evidence import read_current
from .intent import parse_intent
from .paths import intents_dir
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


def preflight(root: Path) -> PreflightResult:
    """Re-run forced-evidence + effort-tier validation over every active intent.

    Walks ``.i2e/intents/*.md`` in alphabetical order, parses each, and runs
    :func:`validate_capability_with_config` against the loaded config and the
    set of currently installed providers. Errors are aggregated per
    capability so the operator sees every problem at once instead of one at
    a time.

    Drafts and retired intents are skipped — drafts are by definition
    work-in-progress, retired intents are frozen.
    """
    root = Path(root)
    cfg = load_config(root)
    providers = installed_provider_names()
    base = intents_dir(root)
    errors: dict[str, list[str]] = {}

    if not base.exists():
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

    # Branch 1: resolved pending files awaiting application.
    if list_resolved_pending(root):
        return ApplyResolutions()

    # Branch 2: an active capability needs develop (new or version-bumped).
    scoped = scoped_capabilities(root)
    if scoped:
        scoped_sorted = sorted(
            (c.frontmatter.capability for c in scoped)
        )
        return DevelopAndEvidence(capability=scoped_sorted[0])

    # Branch 3: a capability has retry-eligible items.
    active = _active_capabilities(root)
    for cap_slug in active:
        try:
            pl = adapt.plan(root, cap_slug)
        except Exception:
            continue
        if pl.retries:
            return AdaptThenRetry(capability=cap_slug)

    # Branch 4: a window has elapsed for some item.
    now = datetime.now(timezone.utc)
    for cap_slug in active:
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


def tick(root: Path) -> TickResult:
    """Run one orchestrator tick. Raises :class:`PreflightFailed` on bad state.

    See the module docstring for the full flow.
    """
    root = Path(root)

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

    # Shippable → leave actions_log empty.

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
        focus = _focus_for_action(action)
        report_link = deep_link(root, focus)

    return TickResult(
        tick_id=tick_id,
        action=action,
        actions_log=actions_log,
        report_path=report_path,
        report_link=report_link,
        shippable=isinstance(action, Shippable),
    )


def _focus_for_action(action: Action) -> str:
    """Return a deep-link fragment matching the action's focus capability."""
    if isinstance(action, DevelopAndEvidence):
        return f"#cap/{action.capability}"
    if isinstance(action, AdaptThenRetry):
        return f"#cap/{action.capability}"
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
