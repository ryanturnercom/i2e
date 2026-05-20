"""Evidence collection runner — the deterministic core of the `i2e-evidence` skill.

Given a Capability, walks every evidence item and constraint, invokes the
named provider for each, and writes:

- ``.i2e/evidence/<cap>/runs/<run-id>.yaml`` — immutable per-run snapshot
- ``.i2e/evidence/<cap>/current.yaml`` — always-rewritten latest verdicts

Returns a :class:`RunSummary` the orchestrator can use to pick the next step.

Provider errors are captured per-item: an exception raised by a provider yields
``ItemVerdict(verdict="fail", raw={"error": str(e)})`` rather than aborting the
whole run. Async providers (``human``, etc.) that raise ``FileExistsError`` on
re-invocation while a pending file is open are silently caught — the existing
pending file is read and either re-emitted (still open) or translated into a
real verdict (resolved) + archived.

See ``i2e_core.pending.resolve_to_verdict`` for the async-resolution mapping
and ``i2e_core.provider.contract.to_item_verdict`` for the sync-result mapping.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field

from .config import load_config
from .evidence import (
    CurrentEvidence,
    ItemVerdict,
    RunSnapshot,
    list_runs,
    read_current,
    read_run,
    write_current,
    write_run_snapshot,
)
from .intent import Capability, Constraint, EvidenceItem, parse_intent
from .paths import intents_dir, pending_dir
from .pending import (
    PendingFile,
    archive_pending,
    read_pending,
    resolve_to_verdict,
)
from .provider import ProviderContext, to_item_verdict
from .provider.discovery import installed_provider_names, load_provider
from .runid import new_run_id
from .validator import ValidationError, validate_capability_with_config


# ---------- RunSummary ----------


class RunSummary(BaseModel):
    """Aggregated verdict counts for a single evidence run.

    ``pass`` is a Python keyword so it can't be used as a field name. We expose
    it as ``pass_`` on the model and as ``"pass"`` in the serialized form via
    a Pydantic alias.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    pass_: int = Field(0, alias="pass")
    fail: int = 0
    met: int = 0
    unmet: int = 0
    trending: int = 0
    awaiting_human: int = 0
    total: int = 0

    @classmethod
    def from_verdicts(cls, verdicts: dict[str, ItemVerdict]) -> "RunSummary":
        counts = {
            "pass_": 0,
            "fail": 0,
            "met": 0,
            "unmet": 0,
            "trending": 0,
            "awaiting_human": 0,
        }
        for v in verdicts.values():
            if v.verdict == "pass":
                counts["pass_"] += 1
            elif v.verdict == "fail":
                counts["fail"] += 1
            elif v.verdict == "met":
                counts["met"] += 1
            elif v.verdict == "unmet":
                counts["unmet"] += 1
            elif v.verdict == "trending":
                counts["trending"] += 1
            elif v.verdict == "awaiting_human":
                counts["awaiting_human"] += 1
        return cls(total=len(verdicts), **counts)

    def compact(self) -> str:
        """One-line summary suitable for the tick log.

        Only non-zero buckets are listed when there is at least one entry to
        show; otherwise the canonical ``"<n> pass, <n> trending, <n> fail"``
        triplet is returned. The default form keeps the headline numbers
        callers expect to scan for.
        """
        return f"{self.pass_} pass, {self.trending} trending, {self.fail} fail"


# ---------- helpers ----------


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _capability_items(cap: Capability) -> list[EvidenceItem | Constraint]:
    """Return every evidence item + every constraint in source order."""
    items: list[EvidenceItem | Constraint] = []
    items.extend(cap.evidence)
    items.extend(cap.constraints)
    return items


def _select_items(
    cap: Capability, only_items: Iterable[str] | None
) -> list[EvidenceItem | Constraint]:
    all_items = _capability_items(cap)
    if only_items is None:
        return all_items
    wanted = set(only_items)
    return [it for it in all_items if it.id in wanted]


def _prev_attempts(
    prior: CurrentEvidence | None, item_id: str
) -> int:
    if prior is None:
        return 0
    v = prior.items.get(item_id)
    if v is None:
        return 0
    return v.attempts_used


def _handle_file_exists(
    root: Path,
    item: EvidenceItem | Constraint,
    prev_attempts: int,
) -> ItemVerdict:
    """Async provider re-raised FileExistsError. Read the existing pending file
    and translate it into an ItemVerdict.
    """
    # Locate the pending file. We don't know the exact basename (date varies),
    # so we glob the pending dir for a file whose capability+item-id suffix
    # matches. There can be at most one per (capability, item).
    pdir = pending_dir(root)
    if not pdir.exists():
        # Shouldn't happen — the provider just told us the file exists. Fall
        # back to a fail verdict rather than crashing the run.
        return ItemVerdict(
            verdict="fail",
            attempts_used=prev_attempts + 1,
            raw={"error": "FileExistsError but pending/ dir is missing"},
        )
    matches = [
        p
        for p in pdir.iterdir()
        if p.is_file()
        and p.suffix == ".yaml"
        and p.name.endswith(f"-{item.id}.yaml")
    ]
    if not matches:
        return ItemVerdict(
            verdict="fail",
            attempts_used=prev_attempts + 1,
            raw={"error": f"FileExistsError but no pending file matches item {item.id!r}"},
        )
    # If multiple match (shouldn't happen), prefer the most recent.
    pending_path = sorted(matches)[-1]
    pf = read_pending(pending_path)
    if pf.status == "open":
        return ItemVerdict(
            verdict="awaiting_human",
            attempts_used=prev_attempts,
            pending=pending_path.name,
        )
    # Resolved → translate, archive, return real verdict.
    verdict = resolve_to_verdict(pf)
    archive_pending(root, pending_path)
    # Preserve attempts_used semantics: a `pass` does not bump attempts; a
    # `fail` resolution does.
    if verdict.verdict == "pass":
        return verdict.model_copy(update={"attempts_used": prev_attempts})
    return verdict.model_copy(update={"attempts_used": prev_attempts + 1})


# ---------- main entry point ----------


def run(
    root: Path,
    capability: str,
    only_items: list[str] | None = None,
) -> RunSummary:
    """Collect evidence for ``capability`` and persist a snapshot + current.yaml.

    See module docstring for the full contract.
    """
    root = Path(root)
    intent_path = intents_dir(root) / f"{capability}.md"
    cap = parse_intent(intent_path)
    cfg = load_config(root)
    providers = installed_provider_names()

    # Preflight: forced-evidence + effort tier check. The orchestrator runs its
    # own preflight, but the runner is also a standalone entry point and must
    # not invoke providers on an invalid intent.
    validate_capability_with_config(cap, cfg, providers)

    prior = read_current(root, capability)
    run_id = new_run_id()
    ctx_base = ProviderContext(
        root=root, capability=capability, run_id=run_id, cfg=cfg
    )

    items_to_run = _select_items(cap, only_items)
    verdicts: dict[str, ItemVerdict] = {}

    for item in items_to_run:
        prev_attempts = _prev_attempts(prior, item.id)
        try:
            provider = load_provider(item.provider)
            result = provider.invoke(item, ctx_base)
        except FileExistsError:
            # Async provider re-raise: a pending file is already on disk.
            verdicts[item.id] = _handle_file_exists(root, item, prev_attempts)
            continue
        except Exception as e:
            verdicts[item.id] = ItemVerdict(
                verdict="fail",
                attempts_used=prev_attempts + 1,
                raw={"error": str(e)},
            )
            continue
        try:
            verdicts[item.id] = to_item_verdict(
                result, prev_attempts=prev_attempts
            )
        except Exception as e:  # defensive — to_item_verdict can raise TypeError
            verdicts[item.id] = ItemVerdict(
                verdict="fail",
                attempts_used=prev_attempts + 1,
                raw={"error": str(e)},
            )

    # If we only ran a subset, carry over prior verdicts for the rest so that
    # the snapshot and current.yaml stay a complete picture of the capability.
    if only_items is not None and prior is not None:
        for id_, v in prior.items.items():
            verdicts.setdefault(id_, v)

    snap = RunSnapshot(
        run_id=run_id,
        capability=capability,
        intent_version=cap.frontmatter.version,
        collected_at=_now_utc(),
        items=verdicts,
    )
    write_run_snapshot(root, snap)
    write_current(
        root,
        CurrentEvidence(
            capability=capability,
            last_run=run_id,
            intent_version=cap.frontmatter.version,
            items=verdicts,
        ),
    )
    return RunSummary.from_verdicts(verdicts)


# ---------- reconcile ----------


def reconcile(root: Path, capability: str) -> CurrentEvidence:
    """Rebuild ``current.yaml`` from the most recent ``runs/*.yaml``.

    Used as a recovery tool when ``current.yaml`` is lost or corrupted. The
    rebuilt file is written to disk so the next read sees a consistent state.
    """
    root = Path(root)
    runs = list_runs(root, capability)
    if not runs:
        raise FileNotFoundError(
            f"No run snapshots found for capability {capability!r}; "
            f"cannot reconcile current.yaml"
        )
    # `list_runs` returns snapshots sorted by filename (alphabetical). Same-day
    # runs share a date prefix but have a random hex suffix, so the alphabetical
    # order does not match write order. Pick the most recently modified file
    # instead — that's the "latest" snapshot in the sense the spec means.
    latest_path = max(runs, key=lambda p: p.stat().st_mtime)
    latest = read_run(latest_path)
    cur = CurrentEvidence(
        capability=latest.capability,
        last_run=latest.run_id,
        intent_version=latest.intent_version,
        items=dict(latest.items),
    )
    write_current(root, cur)
    return cur


# ---------- CLI ----------


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m i2e_core.evidence_runner",
        description="Run evidence collection for a capability.",
    )
    parser.add_argument("capability", help="Capability name (kebab-case)")
    parser.add_argument(
        "--root",
        default=".",
        help="Project root (containing .i2e/). Defaults to cwd.",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=None,
        help="Restrict to specific item ids (repeatable).",
    )
    args = parser.parse_args(argv)

    try:
        summary = run(
            Path(args.root),
            args.capability,
            only_items=args.only,
        )
    except ValidationError as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary.model_dump(by_alias=True), sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - thin CLI shim
    raise SystemExit(_main(sys.argv[1:]))
