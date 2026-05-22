"""Job runner — inline execution with SSE streaming.

The ``run_inline`` function is the test- and production-shared path:
it executes a callable, streams a job-kind SSE event on start and on
every published line, and updates the registry with the final state.

Subprocess support (``spawn``) is included for the production flow,
but tests use ``run_inline`` so they stay deterministic.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from ..sse import ChangeBroker
from .registry import Job, JobRegistry


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def run_inline(
    registry: JobRegistry,
    broker: ChangeBroker,
    job: Job,
    work: Callable[[], int],
) -> Job:
    """Run ``work()`` synchronously; stream start + finish SSE events.

    Returns the final Job with ``state``, ``exit_code``, and
    ``finished_at`` filled in.
    """
    started = job.model_copy(update={"state": "running"})
    registry.register(started)
    broker.notify(kind="job", job_id=job.id, state="running")

    exit_code = 0
    state: str
    try:
        exit_code = int(work())
        state = "completed" if exit_code == 0 else "failed"
    except Exception as exc:
        exit_code = -1
        state = "failed"
        broker.notify(kind="job", job_id=job.id, line=f"ERROR: {exc!r}")

    finished = started.model_copy(
        update={
            "state": state,
            "exit_code": exit_code,
            "finished_at": _now_utc(),
        }
    )
    registry.register(finished)
    broker.notify(kind="job", job_id=job.id, state=state)
    return finished


def spawn(
    registry: JobRegistry,
    broker: ChangeBroker,
    job: Job,
    cmd: list[str],
    *,
    cwd: Path | None = None,
) -> Job:
    """Spawn a subprocess for ``cmd``; stream every stdout line via SSE.

    Synchronous wrapper — waits for the subprocess to exit before
    returning. Production code can call this on a thread; tests prefer
    ``run_inline``.
    """
    started = job.model_copy(update={"state": "running"})
    registry.register(started)

    state = "failed"
    exit_code = -1
    pid: int | None = None
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        pid = proc.pid
        registry.register(started.model_copy(update={"pid": pid}))
        broker.notify(kind="job", job_id=job.id, state="running", pid=pid)

        if proc.stdout is not None:
            for line in proc.stdout:
                broker.notify(kind="job", job_id=job.id, line=line.rstrip())

        proc.wait()
        exit_code = proc.returncode
        state = "completed" if exit_code == 0 else "failed"
    except Exception as exc:
        broker.notify(kind="job", job_id=job.id, line=f"ERROR: {exc!r}")

    finished = started.model_copy(
        update={
            "state": state,
            "exit_code": exit_code,
            "finished_at": _now_utc(),
            "pid": pid,
        }
    )
    registry.register(finished)
    broker.notify(kind="job", job_id=job.id, state=state)
    return finished
