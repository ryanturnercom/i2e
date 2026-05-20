"""Tests for the worktree-dispatch-and-merge slice (swarm-tick §4).

Minimal viable dispatcher: real ``os.makedirs`` claim primitive +
``runtime:`` mirror + threaded worker fan-out, with the actual git
worktree set-up and Agent-tool dispatch deferred to a follow-up slice.
The tests here lock down the lifecycle invariants the eventual
production path will also have to honour.
"""

from __future__ import annotations

import textwrap
import threading
from pathlib import Path

import pytest

from i2e_core import intent
from i2e_core.swarm import (
    DispatchReport,
    dispatch_batch,
    read_claim,
    read_runtime,
    worktree_dir,
)


_INTENT = """---
capability: {name}
created: 2026-05-19
updated: 2026-05-19
version: 1
status: active
watcher: '@me'
touches:
- src/i2e_core/{name_us}.py
- tests/test_{name_us}.py
---

# {name}

## Evidence of success

- id: case-a
  type: case
  provider: pytest
  query: q
  expect: passes
  effort: medium

## Constraints

"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    for sub in ("context", "intents", "evidence", "pending", "logs"):
        (tmp_path / ".i2e" / sub).mkdir(parents=True, exist_ok=True)
    for name in ("alpha", "beta", "gamma"):
        p = tmp_path / ".i2e" / "intents" / f"{name}.md"
        p.write_text(
            textwrap.dedent(
                _INTENT.format(name=name, name_us=name.replace("-", "_"))
            ),
            encoding="utf-8",
        )
    return tmp_path


def test_implemented(project: Path) -> None:
    """The full happy-path lifecycle for a three-slug parallel batch."""
    seen: dict[str, bool] = {}
    seen_runtime: dict[str, dict] = {}
    lock = threading.Lock()

    def worker(slug: str, claim) -> None:
        # While inside the worker, the claim is held AND the runtime
        # mirror is on the intent file. Snapshot both for later asserts.
        with lock:
            seen[slug] = True
            rt = read_runtime(project, slug)
            assert rt is not None, f"{slug}: runtime mirror missing in worker"
            seen_runtime[slug] = rt
            on_disk = read_claim(project, slug)
            assert on_disk is not None and on_disk.slug == slug

    report = dispatch_batch(
        project,
        ["alpha", "beta", "gamma"],
        tick_id="2026-05-20-aaa000",
        worker=worker,
    )

    assert isinstance(report, DispatchReport)
    assert report.ok is True
    assert report.slugs_completed == ["alpha", "beta", "gamma"]
    # Worker ran exactly once per slug.
    assert seen == {"alpha": True, "beta": True, "gamma": True}
    # Each runtime mirror carried the correct tick_id while live.
    for slug, rt in seen_runtime.items():
        assert rt["tick_id"] == "2026-05-20-aaa000"
        assert rt["step"] == "develop"

    # Post-dispatch invariants: claim released AND runtime cleared.
    for slug in ("alpha", "beta", "gamma"):
        assert not worktree_dir(project, slug).exists(), (
            f"{slug}: worktree directory still present after dispatch"
        )
        cap = intent.parse_intent(
            project / ".i2e" / "intents" / f"{slug}.md"
        )
        assert cap.frontmatter.runtime is None, (
            f"{slug}: runtime mirror left dangling on the intent file"
        )


def test_failing_worker_isolates_to_its_slug(project: Path) -> None:
    def worker(slug: str, claim) -> None:
        if slug == "beta":
            raise RuntimeError("simulated worker failure")

    report = dispatch_batch(
        project,
        ["alpha", "beta", "gamma"],
        tick_id="2026-05-20-bbb000",
        worker=worker,
    )
    assert report.ok is False
    by_slug = {r.slug: r for r in report.results}
    assert by_slug["alpha"].ok is True
    assert by_slug["beta"].ok is False
    assert "simulated worker failure" in (by_slug["beta"].error or "")
    assert by_slug["gamma"].ok is True
    # Lock is symmetric: failure releases too.
    for slug in ("alpha", "beta", "gamma"):
        assert not worktree_dir(project, slug).exists()


def test_empty_batch_is_a_no_op(project: Path) -> None:
    called: list[str] = []

    def worker(slug: str, claim) -> None:
        called.append(slug)

    report = dispatch_batch(
        project,
        [],
        tick_id="2026-05-20-ccc000",
        worker=worker,
    )
    assert report.results == []
    assert called == []


def test_single_slug_batch_runs_serially(project: Path) -> None:
    """One-slug batches skip the thread pool — observable only by it working."""
    seen: list[str] = []

    def worker(slug: str, claim) -> None:
        seen.append(slug)

    report = dispatch_batch(
        project,
        ["alpha"],
        tick_id="2026-05-20-ddd000",
        worker=worker,
    )
    assert report.ok is True
    assert seen == ["alpha"]
