"""Console-triggered regression: re-validate cases + constraints.

Wraps ``i2e_core.i2e_regression.run`` in a Job. The job's final tick
entry lands in ``.i2e/logs/`` so the Logs view picks it up.

Scope strings:

- ``"all-shipped"`` — every shipped capability
- ``"slug:<capability>"`` — a single capability
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ... import i2e_regression
from ...runid import new_run_id
from ...tick_log import TickLog, write_tick
from ..jobs.registry import Job, JobRegistry
from ..jobs.runner import run_inline
from ..sse import ChangeBroker


def _parse_scope(scope: str) -> tuple[str, str | None]:
    if scope == "all-shipped":
        return "shipped", None
    if scope.startswith("slug:"):
        return "shipped", scope[len("slug:"):]
    return "shipped", None


def run_regression(
    root: Path,
    *,
    scope: str,
    registry: JobRegistry,
    broker: ChangeBroker,
) -> Job:
    """Run regression inline and write a tick entry on completion."""
    root = Path(root)
    job = Job(
        id=new_run_id(),
        kind="regression",
        scope=scope,
        state="queued",
        started_at=datetime.now(timezone.utc),
    )

    def work() -> int:
        status_scope, capability = _parse_scope(scope)
        result = i2e_regression.run(root, status=status_scope, capability=capability)
        broker.notify(
            kind="job",
            job_id=job.id,
            line=f"regression completed: {len(result.capabilities)} capability deltas",
        )
        # Tick entry so the Logs view surfaces the regression.
        demoted = sum(1 for d in result.capabilities if d.demoted)
        actions = [
            f"regression: scope={scope} caps={len(result.capabilities)} demoted={demoted}"
        ]
        for delta in result.capabilities:
            if delta.demoted:
                actions.append(f"demoted_to_active: {delta.capability}")
        write_tick(
            root,
            TickLog(
                tick_id=new_run_id(),
                ran_at=datetime.now(timezone.utc),
                actions=actions,
            ),
        )
        return 0

    return run_inline(registry, broker, job, work)
