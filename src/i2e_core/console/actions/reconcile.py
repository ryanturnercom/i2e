"""Console-triggered spec reconcile: re-decompose a spec vs its intents.

Wraps ``i2e_core.spec.reconcile`` in a Job. Returns a list of proposed
``ReconcileAction`` items; the orchestrator's next tick applies them
via the existing pending-resolution flow.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ... import spec as spec_core
from ...runid import new_run_id
from ...tick_log import TickLog, write_tick
from ..jobs.registry import Job, JobRegistry
from ..jobs.runner import run_inline
from ..sse import ChangeBroker


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
        broker.notify(
            kind="job",
            job_id=job.id,
            line=f"reconcile produced {len(actions)} proposed action(s)",
        )
        summary = [f"reconcile: spec={spec_slug} actions={len(actions)}"]
        for a in actions:
            summary.append(f"  {a.kind}: {a.capability} ({a.reason})")
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
