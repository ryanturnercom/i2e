"""Console-triggered spec reconcile: re-decompose a spec vs its intents.

Diffs the on-disk spec against the intents that claim it, then materialises
every ``add`` (a spec section with no derived intent yet) as a fresh
``status: draft`` intent under ``.i2e/intents/``. ``edit`` and ``retire``
stay proposed-only — retire flows through the ``i2e-intent`` skill, which has
the LLM context to judge impact (spec §"Decisions locked in").

Boundary note: writing a new draft intent is a deliberate console carve-out,
blessed by the i2e-console spec — the Reconcile button's whole purpose is to
"create a draft for the new section" (spec §Specs view). Existing intents are
never touched: ``reconcile`` only emits ``add`` for capabilities that do not
exist yet, and a draft is written only when no file is already on disk.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ... import spec as spec_core
from ...intent import write_intent
from ...paths import intents_dir, specs_dir
from ...runid import new_run_id
from ...tick_log import TickLog, write_tick
from ..jobs.registry import Job, JobRegistry
from ..jobs.runner import run_inline
from ..sse import ChangeBroker


def _materialise_adds(
    root: Path, spec_slug: str, actions: list[spec_core.ReconcileAction]
) -> list[str]:
    """Write a ``status: draft`` intent for every ``add`` action.

    A ReconcileAction only carries the slug, so the full Capability bodies
    come from re-decomposing the spec. A draft is written only when no
    intent file already exists for that slug — the operation is idempotent
    and never clobbers an operator's edits. Returns the created slugs.
    """
    add_slugs = {a.capability for a in actions if a.kind == "add"}
    if not add_slugs:
        return []
    spec_path = specs_dir(root) / f"{spec_slug}.md"
    if not spec_path.exists():
        return []
    prd = spec_path.read_text(encoding="utf-8")
    base = intents_dir(root)
    base.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for cap in spec_core.decompose(prd, slug=spec_slug):
        slug = cap.frontmatter.capability
        if slug not in add_slugs:
            continue
        path = base / f"{slug}.md"
        if path.exists():
            continue
        write_intent(cap, path)
        created.append(slug)
    return created


def reconcile_spec(
    root: Path,
    spec_slug: str,
    *,
    registry: JobRegistry,
    broker: ChangeBroker,
) -> Job:
    """Reconcile ``spec_slug`` against its derived intents (inline)."""
    root = Path(root)
    job = Job(
        id=new_run_id(),
        kind="reconcile",
        scope=spec_slug,
        state="queued",
        started_at=datetime.now(timezone.utc),
    )

    def work() -> int:
        actions = spec_core.reconcile(root, spec_slug)
        created = _materialise_adds(root, spec_slug, actions)
        broker.notify(
            kind="job",
            job_id=job.id,
            line=(
                f"reconcile produced {len(actions)} proposed action(s); "
                f"created {len(created)} draft(s)"
            ),
        )
        summary = [
            f"reconcile: spec={spec_slug} actions={len(actions)} "
            f"drafts_created={len(created)}"
        ]
        for a in actions:
            note = " -> draft created" if a.capability in created else ""
            summary.append(f"  {a.kind}: {a.capability} ({a.reason}){note}")
        write_tick(
            root,
            TickLog(
                tick_id=new_run_id(),
                ran_at=datetime.now(timezone.utc),
                actions=summary,
            ),
        )
        return 0

    return run_inline(registry, broker, job, work)
