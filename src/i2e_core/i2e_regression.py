"""Periodic case re-validation for shipped (and optionally active) capabilities.

The IDEA loop's branch 4 re-evaluates targets via ``window:`` but has no
analogue for cases — a shipped capability's pytest cases never re-run on
their own. Code rot, dependency upgrades, or external regressions can
silently break a shipped capability without the dashboard noticing.

This module is the deterministic core of the ``i2e-regression`` skill. It
walks shipped (or active, or all) capabilities, re-runs every case +
constraint via ``evidence_runner.run``, and demotes any shipped
capability whose verdicts flipped to ``fail`` / ``unmet`` / ``trending``.
Targets are explicitly out of scope — branch 4 owns that path.

A run-id-keyed log is written to ``.i2e/logs/regressions/<run_id>.yaml``
listing every capability touched and the per-item delta.

CLI: ``python -m i2e_core.i2e_regression --status shipped|active|all
[--capability <slug>]``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from . import evidence_runner
from .evidence import read_current
from .intent import Capability, parse_intent
from .io_utils import atomic_write, dump_yaml
from .paths import i2e_dir, intents_dir
from .runid import new_run_id


# ``shipped`` is the default scope: the loop has no other way to revisit
# its cases. ``active`` is occasionally useful for ad-hoc CI runs.
StatusScope = Literal["shipped", "active", "all"]

# Verdicts that mark a regression. Cases and constraints emit pass/fail;
# the trio matches branch 4's auto-demote contract for symmetry.
_REGRESSION_VERDICTS = frozenset({"fail", "unmet", "trending"})


class ItemDelta(BaseModel):
    """Per-item before/after summary for one capability in a regression run."""

    model_config = ConfigDict(extra="forbid")

    item_id: str
    type: str  # 'case' | 'constraint'
    prior_verdict: str | None
    new_verdict: str
    regressed: bool


class CapabilityDelta(BaseModel):
    """One capability's regression result."""

    model_config = ConfigDict(extra="forbid")

    capability: str
    prior_status: str
    new_status: str
    demoted: bool
    items: list[ItemDelta] = Field(default_factory=list)


class RegressionRun(BaseModel):
    """The aggregated result of a single regression run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    ran_at: datetime
    scope: StatusScope
    capability_filter: str | None
    capabilities: list[CapabilityDelta] = Field(default_factory=list)


# ---------- internal helpers ----------


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _logs_root(root: Path) -> Path:
    return i2e_dir(Path(root)) / "logs" / "regressions"


def _in_scope_statuses(scope: StatusScope) -> frozenset[str]:
    if scope == "shipped":
        return frozenset({"shipped"})
    if scope == "active":
        return frozenset({"active"})
    if scope == "all":
        # ``all`` deliberately excludes draft + retired — those are not
        # part of the operating loop and have no meaningful "shipped"
        # baseline to regress against.
        return frozenset({"active", "shipped"})
    raise ValueError(f"unknown status scope {scope!r}")


def _load_capabilities(
    root: Path,
    *,
    scope: StatusScope,
    capability_filter: str | None,
) -> list[Capability]:
    base = intents_dir(Path(root))
    if not base.exists():
        return []
    allowed = _in_scope_statuses(scope)
    out: list[Capability] = []
    for path in sorted(base.glob("*.md")):
        try:
            cap = parse_intent(path)
        except Exception:
            continue
        if cap.frontmatter.status not in allowed:
            continue
        if capability_filter and cap.frontmatter.capability != capability_filter:
            continue
        out.append(cap)
    out.sort(key=lambda c: c.frontmatter.capability)
    return out


def _case_and_constraint_ids(cap: Capability) -> list[str]:
    """Return only the ids of cases + constraints — targets excluded.

    Constraints are implicit-case items (Pydantic ``Constraint`` model has
    no ``type`` field at the API level, but the runner treats them like
    cases). Targets are skipped per the regression contract.
    """
    ids: list[str] = []
    for ev in cap.evidence:
        if ev.type == "case":
            ids.append(ev.id)
    for cn in cap.constraints:
        ids.append(cn.id)
    return ids


# ---------- main entry point ----------


def run(
    root: Path,
    *,
    status: StatusScope = "shipped",
    capability: str | None = None,
) -> RegressionRun:
    """Re-run case + constraint evidence for in-scope capabilities.

    Targets are NOT re-evaluated — branch 4's ``window:`` mechanism owns
    that. Any shipped capability whose verdicts flip to ``fail`` /
    ``unmet`` / ``trending`` is demoted back to ``active``.

    Returns a :class:`RegressionRun` and writes the same record to
    ``.i2e/logs/regressions/<run_id>.yaml``.
    """
    root = Path(root)
    caps = _load_capabilities(
        root, scope=status, capability_filter=capability
    )

    run_id = new_run_id()
    ran_at = _now_utc()
    deltas: list[CapabilityDelta] = []

    for cap in caps:
        slug = cap.frontmatter.capability
        item_ids = _case_and_constraint_ids(cap)
        if not item_ids:
            # Nothing to re-validate — record an empty delta so the log
            # shows the capability was considered.
            deltas.append(
                CapabilityDelta(
                    capability=slug,
                    prior_status=cap.frontmatter.status,
                    new_status=cap.frontmatter.status,
                    demoted=False,
                    items=[],
                )
            )
            continue

        prior = read_current(root, slug)
        prior_verdicts = (
            {iid: iv.verdict for iid, iv in prior.items.items()}
            if prior
            else {}
        )

        # Re-run only cases + constraints. evidence_runner.run preserves
        # target verdicts in current.yaml since we passed only_items.
        evidence_runner.run(root, slug, only_items=item_ids)

        post = read_current(root, slug)
        post_verdicts = (
            {iid: iv.verdict for iid, iv in post.items.items()}
            if post
            else {}
        )

        # Build per-item deltas only for the items we actually re-ran.
        item_deltas: list[ItemDelta] = []
        regressed_any = False
        item_type_lookup = {ev.id: "case" for ev in cap.evidence if ev.type == "case"}
        for cn in cap.constraints:
            item_type_lookup[cn.id] = "constraint"

        for iid in item_ids:
            new_v = post_verdicts.get(iid, "")
            prior_v = prior_verdicts.get(iid)
            regressed = new_v in _REGRESSION_VERDICTS
            if regressed:
                regressed_any = True
            item_deltas.append(
                ItemDelta(
                    item_id=iid,
                    type=item_type_lookup.get(iid, "case"),
                    prior_verdict=prior_v,
                    new_verdict=new_v,
                    regressed=regressed,
                )
            )

        # Demote shipped → active on any regression.
        prior_status = cap.frontmatter.status
        new_status = prior_status
        demoted = False
        if regressed_any and prior_status == "shipped":
            # Local import: orchestrator owns the carve-out helper so the
            # demotion path stays consistent with branch 4's behavior.
            from .orchestrator import _orchestrator_demote_to_active

            if _orchestrator_demote_to_active(root, slug):
                new_status = "active"
                demoted = True

        deltas.append(
            CapabilityDelta(
                capability=slug,
                prior_status=prior_status,
                new_status=new_status,
                demoted=demoted,
                items=item_deltas,
            )
        )

    result = RegressionRun(
        run_id=run_id,
        ran_at=ran_at,
        scope=status,
        capability_filter=capability,
        capabilities=deltas,
    )
    _write_log(root, result)
    return result


def _write_log(root: Path, result: RegressionRun) -> Path:
    base = _logs_root(root)
    base.mkdir(parents=True, exist_ok=True)
    target = base / f"{result.run_id}.yaml"
    atomic_write(target, dump_yaml(result.model_dump(mode="json")))
    return target


# ---------- CLI ----------


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m i2e_core.i2e_regression",
        description=(
            "Re-run case + constraint evidence for shipped (or active, "
            "or all) capabilities. Targets are out of scope."
        ),
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Project root (containing .i2e/). Defaults to cwd.",
    )
    parser.add_argument(
        "--status",
        choices=("shipped", "active", "all"),
        default="shipped",
        help="Which capabilities to re-validate (default: shipped).",
    )
    parser.add_argument(
        "--capability",
        default=None,
        help="If set, scope to this single capability slug.",
    )
    args = parser.parse_args(argv)

    result = run(
        Path(args.root),
        status=args.status,
        capability=args.capability,
    )
    print(json.dumps(result.model_dump(mode="json"), default=str), flush=True)
    return 0


if __name__ == "__main__":  # pragma: no cover - thin CLI shim
    raise SystemExit(_main(sys.argv[1:]))


__all__ = [
    "CapabilityDelta",
    "ItemDelta",
    "RegressionRun",
    "StatusScope",
    "run",
]
