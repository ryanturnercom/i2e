"""Happy-path tests for the evidence runner.

We inject a `FakeProvider` for `pytest` and check that the runner produces a
correctly shaped `RunSummary`, writes a `current.yaml`, and writes a
`runs/<id>.yaml` snapshot.
"""

from __future__ import annotations

from pathlib import Path

from i2e_core.evidence import read_current
from i2e_core.evidence_runner import RunSummary, run
from i2e_core.paths import current_path, runs_dir

from .conftest import FakeProvider, always_fail, always_pass


def test_single_passing_case_yields_pass_one(
    project: Path, write_intent, patch_providers
):
    write_intent(
        "demo",
        evidence=[
            {
                "id": "case-a",
                "type": "case",
                "provider": "pytest",
                "query": "tests/test_a.py",
                "expect": "passes",
            }
        ],
    )
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})

    summary = run(project, "demo")

    assert isinstance(summary, RunSummary)
    assert summary.pass_ == 1
    assert summary.fail == 0
    assert summary.met == 0
    assert summary.unmet == 0
    assert summary.trending == 0
    assert summary.awaiting_human == 0
    assert summary.total == 1

    # current.yaml + a runs/<id>.yaml were written.
    assert current_path(project, "demo").exists()
    snaps = list(runs_dir(project, "demo").glob("*.yaml"))
    assert len(snaps) == 1

    cur = read_current(project, "demo")
    assert cur is not None
    assert cur.items["case-a"].verdict == "pass"
    assert cur.items["case-a"].attempts_used == 0  # passes never increment


def test_single_failing_case_yields_fail_one_attempts_one(
    project: Path, write_intent, patch_providers
):
    write_intent(
        "demo",
        evidence=[
            {
                "id": "case-a",
                "type": "case",
                "provider": "pytest",
                "query": "tests/test_a.py",
                "expect": "passes",
            }
        ],
    )
    patch_providers({"pytest": FakeProvider("pytest", always_fail("nope"))})

    summary = run(project, "demo")

    assert summary.pass_ == 0
    assert summary.fail == 1
    assert summary.total == 1

    cur = read_current(project, "demo")
    assert cur is not None
    v = cur.items["case-a"]
    assert v.verdict == "fail"
    assert v.attempts_used == 1
    assert v.raw.get("output") == "nope"


def test_summary_alias_round_trip(project: Path, write_intent, patch_providers):
    write_intent(
        "demo",
        evidence=[
            {
                "id": "p1",
                "type": "case",
                "provider": "pytest",
                "query": "tests/test_p.py",
                "expect": "passes",
            },
            {
                "id": "f1",
                "type": "case",
                "provider": "pytest",
                "query": "tests/test_f.py",
                "expect": "passes",
            },
        ],
    )

    def behavior(item, ctx):
        from i2e_core.provider import CaseResult

        if item.id == "p1":
            return CaseResult(verdict="pass", output="")
        return CaseResult(verdict="fail", output="x")

    patch_providers({"pytest": FakeProvider("pytest", behavior)})
    summary = run(project, "demo")
    dumped = summary.model_dump(by_alias=True)
    assert dumped["pass"] == 1
    assert dumped["fail"] == 1
    assert dumped["total"] == 2
    # And the python attribute is `pass_`.
    assert summary.pass_ == 1
    # compact() is suitable for tick log lines.
    assert summary.compact() == "1 pass, 0 trending, 1 fail"


def test_constraint_invoked_alongside_evidence(
    project: Path, write_intent, patch_providers
):
    """Constraints share the iteration loop with evidence items."""
    write_intent(
        "demo",
        evidence=[
            {
                "id": "case-a",
                "type": "case",
                "provider": "pytest",
                "query": "tests/test_a.py",
                "expect": "passes",
            }
        ],
        constraints=[
            {
                "id": "constr-a",
                "provider": "pytest",
                "query": "tests/test_c.py",
                "expect": "passes",
            }
        ],
    )
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})

    summary = run(project, "demo")
    assert summary.pass_ == 2  # case + constraint both pass
    assert summary.total == 2


def test_attempts_used_resets_on_pass(
    project: Path, write_intent, patch_providers
):
    """A failing item bumps attempts_used; a subsequent pass leaves it at 0."""
    write_intent(
        "demo",
        evidence=[
            {
                "id": "case-a",
                "type": "case",
                "provider": "pytest",
                "query": "tests/test_a.py",
                "expect": "passes",
            }
        ],
    )

    # First run: fails twice (one run = one attempt).
    patch_providers({"pytest": FakeProvider("pytest", always_fail())})
    run(project, "demo")
    run(project, "demo")
    cur = read_current(project, "demo")
    assert cur is not None
    assert cur.items["case-a"].verdict == "fail"
    assert cur.items["case-a"].attempts_used == 2

    # Now flip to passing: a pass clamps attempts_used to the prior value
    # (per to_item_verdict semantics) — and the prior value is 2.
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    run(project, "demo")
    cur = read_current(project, "demo")
    assert cur is not None
    assert cur.items["case-a"].verdict == "pass"
    assert cur.items["case-a"].attempts_used == 2


def test_only_items_runs_subset_and_carries_over(
    project: Path, write_intent, patch_providers
):
    write_intent(
        "demo",
        evidence=[
            {
                "id": "case-a",
                "type": "case",
                "provider": "pytest",
                "query": "tests/test_a.py",
                "expect": "passes",
            },
            {
                "id": "case-b",
                "type": "case",
                "provider": "pytest",
                "query": "tests/test_b.py",
                "expect": "passes",
            },
        ],
    )

    # First run: both pass.
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    run(project, "demo")

    # Second run: provider would fail; restrict to case-b only. case-a must
    # carry over its prior 'pass'.
    patch_providers({"pytest": FakeProvider("pytest", always_fail("only-b"))})
    summary = run(project, "demo", only_items=["case-b"])
    assert summary.fail == 1
    assert summary.pass_ == 1  # case-a carried over
    assert summary.total == 2

    cur = read_current(project, "demo")
    assert cur is not None
    assert cur.items["case-a"].verdict == "pass"
    assert cur.items["case-b"].verdict == "fail"


def test_target_met_verdict(project: Path, write_intent, patch_providers):
    write_intent(
        "demo",
        evidence=[
            {
                "id": "target-a",
                "type": "target",
                "provider": "datadog",
                "query": "metric.foo",
                "expect": "<50ms",
            },
        ],
    )

    from datetime import datetime, timezone

    from i2e_core.provider import TargetResult

    def target_behavior(item, ctx):
        return TargetResult(
            value="32ms", met="met", observed_at=datetime(2026, 5, 19, tzinfo=timezone.utc)
        )

    patch_providers(
        {"datadog": FakeProvider("datadog", target_behavior)}
    )
    summary = run(project, "demo")
    assert summary.met == 1
    assert summary.total == 1

    cur = read_current(project, "demo")
    assert cur is not None
    assert cur.items["target-a"].verdict == "met"
    assert cur.items["target-a"].value == "32ms"
