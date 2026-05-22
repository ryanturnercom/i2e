"""In-memory Job tracker.

Threading note: the registry is guarded by a single lock; mutations
take the lock for the duration of a register / update / cleanup call.
"""

from __future__ import annotations

import os
import signal
import threading
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

JobKind = Literal["regression", "reconcile"]
JobState = Literal["queued", "running", "completed", "failed"]

_FINISHED_STATES: frozenset[JobState] = frozenset({"completed", "failed"})


class Job(BaseModel):
    """One console-triggered long-running operation."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: JobKind
    scope: str
    state: JobState
    started_at: datetime
    finished_at: datetime | None = None
    exit_code: int | None = None
    pid: int | None = None


class JobRegistry:
    """Thread-safe in-memory dict of ``Job`` objects keyed by id."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def register(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.id] = job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **fields) -> Job | None:
        with self._lock:
            current = self._jobs.get(job_id)
            if current is None:
                return None
            updated = current.model_copy(update=fields)
            self._jobs[job_id] = updated
            return updated

    def list_jobs(self) -> list[Job]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.started_at, reverse=True)

    def cleanup_finished(self) -> int:
        """Drop completed/failed jobs from the registry. Returns count dropped."""
        with self._lock:
            keep = {
                jid: j for jid, j in self._jobs.items() if j.state not in _FINISHED_STATES
            }
            dropped = len(self._jobs) - len(keep)
            self._jobs = keep
            return dropped

    def kill_running(self) -> int:
        """Send SIGTERM to every running job's PID. Returns count signalled."""
        signalled = 0
        with self._lock:
            jobs = [j for j in self._jobs.values() if j.state == "running" and j.pid]
        for j in jobs:
            try:
                os.kill(j.pid, signal.SIGTERM)
                signalled += 1
            except (OSError, ProcessLookupError):
                continue
        return signalled
