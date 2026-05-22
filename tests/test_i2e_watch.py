"""Tests for the `i2e-watch` watcher core (`i2e_core.watch`)."""

from __future__ import annotations

import json
import textwrap
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from i2e_core import watch
from i2e_core.swarm import Claim, acquire_claim, claim_path, worktree_dir


_INTENT = """---
capability: {name}
created: 2026-05-22
updated: 2026-05-22
version: {version}
status: {status}
watcher: '@me'
{deps}{touches}---

# {name}

## Evidence of success

- id: case-a
  type: case
  provider: pytest
  query: tests/test_{name}.py::test_x
  expect: passes
  effort: medium

## Constraints

"""


def _deps(items: list[str] | None) -> str:
    if not items:
        return ""
    rendered = "\n".join(f"  - {i}" for i in items)
    return f"depends_on:\n{rendered}\n"


def _touches(items: list[str] | None) -> str:
    if not items:
        return ""
    rendered = "\n".join(f"  - {i!r}" for i in items)
    return f"touches:\n{rendered}\n"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    for sub in ("context", "intents", "evidence", "pending", "logs"):
        (tmp_path / ".i2e" / sub).mkdir(parents=True, exist_ok=True)
    return tmp_path


def _write(
    project: Path,
    name: str,
    *,
    version: int = 1,
    status: str = "active",
    touches: list[str] | None = None,
    depends_on: list[str] | None = None,
) -> Path:
    body = _INTENT.format(
        name=name,
        version=version,
        status=status,
        deps=_deps(depends_on),
        touches=_touches(touches or [f"src/{name}/**"]),
    )
    p = project / ".i2e" / "intents" / f"{name}.md"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


# ---------- plan() ----------


def test_plan_empty_project_is_empty_batch(project: Path) -> None:
    b = watch.plan(project)
    assert b.batch == []
    assert b.remaining == []
    assert b.reason == "initial"


def test_plan_new_intent_triggers(project: Path) -> None:
    _write(project, "alpha")
    b = watch.plan(project)
    assert b.batch == ["alpha"]
    assert b.max_concurrent == 4  # config default


def test_plan_draft_intent_ignored(project: Path) -> None:
    _write(project, "alpha", status="draft")
    assert watch.plan(project).batch == []


def test_plan_caps_at_max_concurrent(project: Path) -> None:
    for i in range(6):
        _write(project, f"c{i}")  # distinct touches per capability
    b = watch.plan(project, max_concurrent=4)
    assert len(b.batch) == 4
    assert b.batch == ["c0", "c1", "c2", "c3"]
    assert b.remaining == ["c4", "c5"]


def test_plan_overlapping_touches_defers(project: Path) -> None:
    _write(project, "alpha", touches=["src/shared/**"])
    _write(project, "beta", touches=["src/shared/**"])
    b = watch.plan(project)
    assert b.batch == ["alpha"]  # alphabetical winner keeps the slot
    assert b.remaining == ["beta"]


def test_plan_depends_on_holds_child_back(project: Path) -> None:
    _write(project, "parent")
    _write(project, "child", depends_on=["parent"])
    b = watch.plan(project)
    assert b.batch == ["parent"]
    # The child is dep-blocked — neither dispatched nor queued as remaining.
    assert "child" not in b.remaining


def test_plan_skips_live_claim(project: Path) -> None:
    _write(project, "alpha")
    _write(project, "beta")
    # A live claim owned by this process — alpha is in flight.
    acquire_claim(project, "alpha", tick_id="t1", step="develop")
    b = watch.plan(project)
    assert "alpha" not in b.batch
    assert b.batch == ["beta"]


def test_plan_stale_claim_does_not_block(project: Path) -> None:
    _write(project, "alpha")
    # A claim naming a long-dead PID is stale — it must not block dispatch.
    wd = worktree_dir(project, "alpha")
    wd.mkdir(parents=True, exist_ok=True)
    stale = Claim(
        slug="alpha",
        agent_id="ghost",
        pid=999_999,
        tick_id="t0",
        step="develop",
        started_at=datetime.now(timezone.utc),
    )
    claim_path(project, "alpha").write_text(
        json.dumps(stale.model_dump(mode="json")), encoding="utf-8"
    )
    assert watch.plan(project).batch == ["alpha"]


def test_plan_skips_malformed_intent(project: Path) -> None:
    _write(project, "alpha")
    (project / ".i2e" / "intents" / "broken.md").write_text(
        "---\ncapability: [unclosed\n", encoding="utf-8"
    )
    # The malformed file is skipped; the good one still plans.
    assert watch.plan(project).batch == ["alpha"]


# ---------- watch state ----------


def test_next_batch_records_state_and_does_not_retrigger(
    project: Path,
) -> None:
    _write(project, "alpha")
    b = watch.next_batch(project, timeout=5.0)
    assert b.batch == ["alpha"]
    # State file now records the dispatched version.
    state = json.loads(
        watch.watch_state_path(project).read_text(encoding="utf-8")
    )
    assert state == {"alpha": 1}
    # A second plan sees no trigger — same version, already dispatched.
    assert watch.plan(project).batch == []
    assert watch.plan(project).reason == "intent-change"


def test_version_bump_retriggers(project: Path) -> None:
    _write(project, "alpha", version=1)
    watch.next_batch(project, timeout=5.0)
    assert watch.plan(project).batch == []
    # Bumping the intent version re-arms the trigger.
    _write(project, "alpha", version=2)
    assert watch.plan(project).batch == ["alpha"]


def test_corrupt_state_file_ignored(project: Path) -> None:
    _write(project, "alpha")
    watch.watch_state_path(project).write_text("{not json", encoding="utf-8")
    # A corrupt state file is treated as empty, not a crash.
    assert watch.plan(project).batch == ["alpha"]


# ---------- next_batch blocking ----------


def test_next_batch_times_out_when_idle(project: Path) -> None:
    b = watch.next_batch(project, timeout=0.3)
    assert b.timed_out is True
    assert b.batch == []
    assert b.reason == "timeout"


def test_next_batch_wakes_on_intent_change(project: Path) -> None:
    def _writer() -> None:
        time.sleep(0.4)
        _write(project, "alpha")

    t = threading.Thread(target=_writer)
    t.start()
    try:
        b = watch.next_batch(project, timeout=10.0)
    finally:
        t.join()
    assert b.timed_out is False
    assert b.batch == ["alpha"]


# ---------- CLI ----------


def test_cli_plan(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(project, "alpha")
    rc = watch._main(["plan", "--root", str(project)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["batch"] == ["alpha"]
    # plan must not write the state file.
    assert not watch.watch_state_path(project).exists()


def test_cli_next_timeout(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = watch._main(["next", "--root", str(project), "--timeout", "0.3"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["timed_out"] is True


def test_cli_next_with_max_override(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for i in range(3):
        _write(project, f"c{i}")
    rc = watch._main(
        ["next", "--root", str(project), "--max", "2", "--timeout", "5"]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["max_concurrent"] == 2
    assert len(payload["batch"]) == 2
    assert payload["remaining"] == ["c2"]
