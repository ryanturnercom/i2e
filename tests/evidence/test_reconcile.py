"""`reconcile` rebuilds current.yaml from the latest snapshot."""

from __future__ import annotations

from pathlib import Path

import pytest

from i2e_core.evidence import read_current
from i2e_core.evidence_runner import reconcile, run
from i2e_core.paths import current_path

from .conftest import FakeProvider, always_pass


def test_reconcile_reproduces_current_from_latest_snapshot(
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
    run(project, "demo")
    expected = read_current(project, "demo")
    assert expected is not None

    # Delete current.yaml to simulate corruption.
    current_path(project, "demo").unlink()
    assert read_current(project, "demo") is None

    rebuilt = reconcile(project, "demo")
    assert rebuilt.items == expected.items
    assert rebuilt.last_run == expected.last_run
    assert rebuilt.intent_version == expected.intent_version

    # And current.yaml is back on disk.
    again = read_current(project, "demo")
    assert again is not None
    assert again == rebuilt


def test_reconcile_with_no_snapshots_raises(project: Path):
    """No runs/ directory at all → FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        reconcile(project, "no-such-cap")


def test_reconcile_uses_latest_run_when_multiple_exist(
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
    run(project, "demo")
    run(project, "demo")
    expected = read_current(project, "demo")
    assert expected is not None

    current_path(project, "demo").unlink()
    rebuilt = reconcile(project, "demo")
    assert rebuilt.last_run == expected.last_run
