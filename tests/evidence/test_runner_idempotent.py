"""Re-running on the same intent yields a NEW snapshot but updates current.yaml.last_run."""

from __future__ import annotations

from pathlib import Path

from i2e_core.evidence import read_current
from i2e_core.evidence_runner import run
from i2e_core.paths import runs_dir

from .conftest import FakeProvider, always_pass


def test_two_runs_produce_two_snapshots_same_intent_version(
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
    cur1 = read_current(project, "demo")
    assert cur1 is not None
    first_last_run = cur1.last_run

    # Note: new_run_id() uses a random hex suffix so two same-day runs almost
    # always have different ids. If by cosmic accident they collide, the
    # write_run_snapshot path would raise FileExistsError (and the test would
    # fail noisily, which is the right behaviour to surface).
    run(project, "demo")
    cur2 = read_current(project, "demo")
    assert cur2 is not None
    second_last_run = cur2.last_run

    assert first_last_run != second_last_run
    assert cur2.intent_version == 1  # version didn't change

    # Both snapshots are on disk; they're immutable.
    snaps = sorted(runs_dir(project, "demo").glob("*.yaml"))
    assert len(snaps) == 2


def test_run_snapshot_is_immutable(project: Path, write_intent, patch_providers, monkeypatch):
    """If the same run-id were generated twice (force this), the second write raises."""
    from i2e_core import evidence_runner

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

    # Force new_run_id to be deterministic so the second run collides.
    monkeypatch.setattr(
        evidence_runner, "new_run_id", lambda: "2026-05-19-abc123"
    )

    run(project, "demo")  # writes snapshot
    # Second run with the same id must refuse to overwrite the snapshot.
    import pytest as _pt

    with _pt.raises(FileExistsError):
        run(project, "demo")


def test_current_yaml_byte_for_byte_matches_latest_snapshot(
    project: Path, write_intent, patch_providers
):
    """The verdicts written to current.yaml must equal those in runs/<id>.yaml."""
    from i2e_core.evidence import read_run

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
    cur = read_current(project, "demo")
    assert cur is not None
    snaps = sorted(runs_dir(project, "demo").glob("*.yaml"))
    snap = read_run(snaps[-1])
    assert cur.items == snap.items
    assert cur.last_run == snap.run_id
    assert cur.intent_version == snap.intent_version
