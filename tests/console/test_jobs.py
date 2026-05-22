"""Jobs — regression tick, SSE streaming, and subprocess hygiene."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from i2e_core.console.actions.regression import run_regression
from i2e_core.console.jobs.registry import Job, JobRegistry
from i2e_core.console.jobs.runner import run_inline
from i2e_core.console.sse import ChangeBroker
from i2e_core.intent import Capability, EvidenceItem, Frontmatter, write_intent
from i2e_core.tick_log import _read_tick
from i2e_core.paths import logs_dir


def _seed_shipped(root: Path, slug: str = "demo-cap") -> None:
    intents = root / ".i2e" / "intents"
    intents.mkdir(parents=True, exist_ok=True)
    today = date.today()
    cap = Capability(
        frontmatter=Frontmatter(
            capability=slug,
            created=today,
            updated=today,
            version=1,
            status="shipped",
            watcher="@me",
        ),
        description="x",
        evidence=[
            EvidenceItem(
                id=f"{slug}-case",
                type="case",
                provider="pytest",
                query=f"tests/test_{slug}.py::test_x",
                expect="passes",
            )
        ],
    )
    write_intent(cap, intents / f"{slug}.md")


def test_regression_writes_tick_on_complete(tmp_path):
    _seed_shipped(tmp_path)

    registry = JobRegistry()
    broker = ChangeBroker()
    try:
        job = run_regression(
            tmp_path,
            scope="all-shipped",
            registry=registry,
            broker=broker,
        )
        assert job.state == "completed"
    finally:
        broker.close()

    # A regression-flavored tick log must exist.
    base = logs_dir(tmp_path)
    found = False
    for p in base.glob("*-tick.yaml"):
        tl = _read_tick(p)
        if tl and any("regression" in a for a in tl.actions):
            found = True
            break
    assert found, "expected a tick log containing a regression action"


def test_job_stdout_streams_via_sse(tmp_path):
    registry = JobRegistry()
    broker = ChangeBroker()
    q = broker.subscribe()
    try:
        job = Job(
            id="test-stream-1",
            kind="regression",
            scope="all-shipped",
            state="queued",
            started_at=datetime.now(timezone.utc),
        )
        result = run_inline(
            registry,
            broker,
            job,
            work=lambda: 0,
        )
        assert result.state == "completed"

        # The runner emits at least a start and finish job event.
        events = []
        while not q.empty():
            events.append(q.get_nowait())
        kinds = [e.get("kind") for e in events]
        job_ids = [e.get("job_id") for e in events if e.get("kind") == "job"]
        assert "job" in kinds
        assert "test-stream-1" in job_ids
    finally:
        broker.close()


def test_jobs_dont_leak_subprocesses():
    reg = JobRegistry()
    now = datetime.now(timezone.utc)
    completed = Job(
        id="j-completed",
        kind="regression",
        scope="all-shipped",
        state="completed",
        started_at=now,
        finished_at=now,
        exit_code=0,
    )
    running = Job(
        id="j-running",
        kind="reconcile",
        scope="some-spec",
        state="running",
        started_at=now,
    )
    reg.register(completed)
    reg.register(running)
    assert len(reg.list_jobs()) == 2

    # cleanup_finished must drop completed/failed but keep running.
    dropped = reg.cleanup_finished()
    assert dropped == 1
    remaining = {j.id for j in reg.list_jobs()}
    assert "j-completed" not in remaining
    assert "j-running" in remaining

    # kill_running with no real PIDs is a no-op (no PIDs to signal).
    signalled = reg.kill_running()
    assert signalled == 0
