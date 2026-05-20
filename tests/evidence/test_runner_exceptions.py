"""Provider exceptions must not crash the run."""

from __future__ import annotations

from pathlib import Path

from i2e_core.evidence import read_current
from i2e_core.evidence_runner import run

from .conftest import FakeProvider, always_pass, always_raise


def test_provider_exception_captured_as_fail(
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
    patch_providers(
        {"pytest": FakeProvider("pytest", always_raise(RuntimeError("kaboom")))}
    )

    summary = run(project, "demo")
    assert summary.fail == 1
    assert summary.total == 1

    cur = read_current(project, "demo")
    assert cur is not None
    v = cur.items["case-a"]
    assert v.verdict == "fail"
    assert v.attempts_used == 1
    assert v.raw.get("error") == "kaboom"


def test_one_provider_raises_others_still_run(
    project: Path, write_intent, patch_providers
):
    write_intent(
        "demo",
        evidence=[
            {
                "id": "good",
                "type": "case",
                "provider": "pytest",
                "query": "tests/test_g.py",
                "expect": "passes",
            },
            {
                "id": "bad",
                "type": "case",
                "provider": "buggy",
                "query": "anything",
                "expect": "passes",
            },
        ],
    )
    patch_providers(
        {
            "pytest": FakeProvider("pytest", always_pass()),
            "buggy": FakeProvider("buggy", always_raise(ValueError("nope"))),
        }
    )

    summary = run(project, "demo")
    assert summary.pass_ == 1
    assert summary.fail == 1
    assert summary.total == 2

    cur = read_current(project, "demo")
    assert cur is not None
    assert cur.items["good"].verdict == "pass"
    assert cur.items["bad"].verdict == "fail"
    assert cur.items["bad"].raw.get("error") == "nope"


def test_validation_error_propagates(project: Path, write_intent, patch_providers):
    """A capability referencing an uninstalled provider must NOT silently run."""
    from i2e_core.validator import ValidationError

    write_intent(
        "demo",
        evidence=[
            {
                "id": "case-a",
                "type": "case",
                "provider": "nonexistent",
                "query": "x",
                "expect": "y",
            }
        ],
    )
    # Only install "pytest" — "nonexistent" is unknown to the validator.
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    import pytest as _pt

    with _pt.raises(ValidationError):
        run(project, "demo")
