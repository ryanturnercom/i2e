"""Tests for the develop fan-out planner (spec §4.1, §11)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from i2e_core import intent
from i2e_core.develop import (
    DevelopPlan,
    FileGoal,
    execute_plan,
    plan_develop,
)


def _evidence(id_: str, query: str) -> intent.EvidenceItem:
    return intent.EvidenceItem(
        id=id_,
        type="case",
        provider="pytest",
        query=query,
        expect="passes",
        effort="medium",
    )


def _cap(
    name: str,
    *,
    evidence: list[intent.EvidenceItem],
    constraints: list[intent.Constraint] | None = None,
    touches: list[str] | None = None,
) -> intent.Capability:
    fm_kwargs: dict = dict(
        capability=name,
        created=date(2026, 5, 19),
        updated=date(2026, 5, 19),
        version=1,
        status="active",
        watcher="@me",
    )
    if touches is not None:
        fm_kwargs["touches"] = touches
    return intent.Capability(
        frontmatter=intent.Frontmatter(**fm_kwargs),
        description="d",
        evidence=evidence,
        constraints=constraints or [],
    )


def test_planner_groups_independent_files_into_parallel_batch() -> None:
    cap = _cap(
        "tri",
        evidence=[
            _evidence("a", "tests/test_a.py::test_one"),
            _evidence("b", "tests/test_b.py::test_one"),
            _evidence("c", "tests/test_c.py::test_one"),
        ],
        touches=["tests/**"],
    )
    plan = plan_develop(cap)
    assert len(plan.batches) == 1
    assert len(plan.batches[0]) == 3
    assert plan.is_fanout is True
    paths = sorted(str(g.path).replace("\\", "/") for g in plan.batches[0])
    assert paths == ["tests/test_a.py", "tests/test_b.py", "tests/test_c.py"]


def test_planner_serializes_goals_on_same_file() -> None:
    cap = _cap(
        "shared",
        evidence=[
            _evidence("first", "tests/test_shared.py::test_one"),
            _evidence("second", "tests/test_shared.py::test_two"),
        ],
        touches=["tests/**"],
    )
    plan = plan_develop(cap)
    # Two items, same file -> two sequential batches of one goal each.
    assert len(plan.batches) == 2
    assert all(len(b) == 1 for b in plan.batches)
    assert plan.is_fanout is False  # no batch has > 1 goal
    ids_in_order = [b[0].item_ids[0] for b in plan.batches]
    assert ids_in_order == ["first", "second"]


def test_parallel_writes_merge_into_consistent_src_state(
    tmp_path: Path,
) -> None:
    cap = _cap(
        "merge",
        evidence=[
            _evidence("alpha", "tests/test_alpha.py::test_one"),
            _evidence("beta", "tests/test_beta.py::test_one"),
            _evidence("gamma", "tests/test_gamma.py::test_one"),
        ],
        touches=["tests/**"],
    )
    plan = plan_develop(cap)
    # Sanity: this scenario must actually fan out, otherwise the test is moot.
    assert plan.is_fanout is True

    def writer(g: FileGoal) -> str:
        return f"# {g.item_ids[0]}\n"

    report = execute_plan(plan, writer, root=tmp_path)
    assert report.ok
    # Every distinct goal file is written exactly once.
    assert sorted(report.paths_written) == [
        "tests/test_alpha.py",
        "tests/test_beta.py",
        "tests/test_gamma.py",
    ]
    for name, want_id in [
        ("test_alpha.py", "alpha"),
        ("test_beta.py", "beta"),
        ("test_gamma.py", "gamma"),
    ]:
        body = (tmp_path / "tests" / name).read_text(encoding="utf-8")
        assert want_id in body


def test_planner_never_emits_goal_outside_touches() -> None:
    cap = _cap(
        "scoped",
        evidence=[
            _evidence("in-scope", "tests/scoped/test_ok.py::test_one"),
            _evidence("out-of-scope", "tests/other/test_leak.py::test_one"),
        ],
        touches=["tests/scoped/**"],
    )
    plan = plan_develop(cap)
    # The out-of-scope item must not appear in any batch.
    emitted_ids = {
        item_id
        for batch in plan.batches
        for goal in batch
        for item_id in goal.item_ids
    }
    assert "out-of-scope" not in emitted_ids
    assert "in-scope" in emitted_ids
    # And the skipped list explains exactly why.
    skipped_ids = {sid for sid, _ in plan.skipped_out_of_scope}
    assert skipped_ids == {"out-of-scope"}


def test_spec_documents_develop_fanout() -> None:
    spec = (
        Path(__file__).resolve().parent.parent
        / ".documentation"
        / "I2E_simplified.md"
    )
    text = spec.read_text(encoding="utf-8")
    section_41 = text.split("### 4.1")[1].split("### 4.2")[0]
    section_11 = text.split("## 11.")[1].split("## 12.")[0]
    # §4.1 must describe i2e-develop's fan-out behaviour.
    assert (
        "fan-out" in section_41.lower()
        or "fanout" in section_41.lower()
        or "parallel" in section_41.lower()
    )
    # §11 must state the new principle.
    assert "Parallelize within capability" in section_11


def test_capability_with_one_file_runs_without_fanout_overhead(
    tmp_path: Path,
) -> None:
    cap = _cap(
        "solo",
        evidence=[_evidence("only", "tests/test_solo.py::test_one")],
        touches=["tests/**"],
    )
    plan = plan_develop(cap)
    # One batch, one goal, no parallel slot.
    assert len(plan.batches) == 1
    assert len(plan.batches[0]) == 1
    assert plan.is_fanout is False

    # Executing also walks the single-goal short-circuit path without
    # spinning up a ThreadPoolExecutor — the test asserts the result is
    # consistent, which is the observable effect of "no overhead".
    report = execute_plan(plan, lambda g: "content\n", root=tmp_path)
    assert report.ok
    assert report.paths_written == ["tests/test_solo.py"]
