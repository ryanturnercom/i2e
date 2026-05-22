"""End-to-end tick tests — each decision branch wired through ``tick``."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from i2e_core.evidence import read_current
from i2e_core.orchestrator import (
    AdaptThenRetry,
    ApplyResolutions,
    DevelopAndEvidence,
    PreflightFailed,
    ReEvaluateItem,
    Shippable,
    tick,
)
from i2e_core.paths import logs_dir, pending_dir
from i2e_core.pending import PendingFile, write_pending

from .conftest import FakeProvider, always_fail, always_pass, target_met


def _basic_evidence() -> list[dict]:
    return [
        {
            "id": "case-a",
            "type": "case",
            "provider": "pytest",
            "query": "tests/test_a.py",
            "expect": "passes",
            "effort": "medium",
        }
    ]


# ---------- Branch 5 (no-op) ----------


def test_tick_shippable_writes_nothing(
    project: Path, write_intent, write_current_for, patch_providers
):
    """An already-shipped project ticks to Shippable with no side effects.

    Active + all-green capabilities auto-promote to shipped on the next
    tick (§6.1, intent-shipped-status), so we set the capability up as
    shipped from the start to exercise the steady state.
    """
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent("alpha", evidence=_basic_evidence(), version=1, status="shipped")
    write_current_for(
        "alpha",
        {"case-a": {"verdict": "pass", "attempts_used": 0}},
        intent_version=1,
    )
    result = tick(project)
    assert isinstance(result.action, Shippable)
    assert result.shippable is True
    assert result.actions_log == []
    assert result.report_path is None
    # No tick-log files written.
    assert list(logs_dir(project).glob("*-tick.yaml")) == []


# ---------- Branch 2 (DevelopAndEvidence) ----------


def test_tick_develop_and_evidence_writes_log_and_calls_report(
    project: Path, write_intent, patch_providers, monkeypatch
):
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent("alpha", evidence=_basic_evidence(), version=1)

    rendered: list[Path] = []

    def fake_render(root: Path) -> Path:
        rendered.append(Path(root))
        return Path(root) / ".i2e" / "report.html"

    monkeypatch.setattr("i2e_core.orchestrator.render", fake_render)

    result = tick(project)
    assert isinstance(result.action, DevelopAndEvidence)
    assert result.action.capability == "alpha"
    assert result.shippable is False

    # Two actions: ran_develop, ran_evidence.
    assert any(a.startswith("ran_develop:") for a in result.actions_log)
    assert any(a.startswith("ran_evidence:") for a in result.actions_log)

    # Tick log file was written.
    tick_files = list(logs_dir(project).glob("*-tick.yaml"))
    assert len(tick_files) == 1
    # Report rendered exactly once.
    assert len(rendered) == 1
    assert result.report_path is not None

    # Evidence side-effects landed.
    cur = read_current(project, "alpha")
    assert cur is not None
    assert cur.items["case-a"].verdict == "pass"


# ---------- Branch 1 (ApplyResolutions) ----------


def test_tick_apply_resolutions_archives_pending_file(
    project: Path, write_intent, write_current_for, patch_providers, monkeypatch
):
    """Branch 1 calls ``adapt.apply_resolutions`` which archives the file
    into ``.i2e/logs/``."""
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent("alpha", evidence=_basic_evidence(), version=1)
    # apply_resolutions choice 4 (accept) needs a current.yaml to mutate.
    write_current_for(
        "alpha",
        {"case-a": {"verdict": "fail", "attempts_used": 1}},
        intent_version=1,
    )
    pf = PendingFile(
        status="resolved",
        kind="escalation",
        capability="alpha",
        item_id="case-a",
        escalated_at=datetime.now(timezone.utc),
        ask="?",
        resolution="4",
    )
    pending_path = write_pending(project, pf)

    monkeypatch.setattr(
        "i2e_core.orchestrator.render",
        lambda root: Path(root) / ".i2e" / "report.html",
    )

    result = tick(project)
    assert isinstance(result.action, ApplyResolutions)
    assert any(
        a.startswith("applied_resolution: alpha / case-a")
        for a in result.actions_log
    )
    # Pending file moved to logs/.
    assert not pending_path.exists()
    moved = logs_dir(project) / pending_path.name
    assert moved.exists()


# ---------- Branch 3 (AdaptThenRetry) ----------


def test_tick_adapt_retry_records_action_and_does_not_escalate_with_budget(
    project: Path, write_intent, write_current_for, patch_providers, monkeypatch
):
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent("alpha", evidence=_basic_evidence(), version=1)
    write_current_for(
        "alpha",
        {"case-a": {"verdict": "fail", "attempts_used": 2}},  # medium → max 6
        intent_version=1,
    )
    monkeypatch.setattr(
        "i2e_core.orchestrator.render", lambda root: None
    )
    result = tick(project)
    assert isinstance(result.action, AdaptThenRetry)
    assert any(a.startswith("ran_adapt: alpha") for a in result.actions_log)
    # No pending files written (budget remains).
    pdir = pending_dir(project)
    assert list(pdir.glob("*.yaml")) == []


def test_tick_adapt_escalates_when_budget_exhausted(
    project: Path, write_intent, write_current_for, patch_providers, monkeypatch
):
    """When ``plan`` returns retries AND escalations, ``tick`` writes escalation
    pending files for the exhausted items."""
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    # Two evidence items so we can have one retrying and one escalating.
    write_intent(
        "alpha",
        evidence=[
            {
                "id": "case-a",
                "type": "case",
                "provider": "pytest",
                "query": "q",
                "expect": "passes",
                "effort": "medium",  # max=6
            },
            {
                "id": "case-b",
                "type": "case",
                "provider": "pytest",
                "query": "q",
                "expect": "passes",
                "effort": "low",  # max=3
            },
        ],
        version=1,
    )
    write_current_for(
        "alpha",
        {
            "case-a": {"verdict": "fail", "attempts_used": 2},   # retry
            "case-b": {"verdict": "fail", "attempts_used": 3},   # escalate
        },
        intent_version=1,
    )
    monkeypatch.setattr("i2e_core.orchestrator.render", lambda root: None)
    result = tick(project)
    assert isinstance(result.action, AdaptThenRetry)
    # An escalation pending file was created for case-b.
    pending_files = list(pending_dir(project).glob("*.yaml"))
    assert len(pending_files) == 1
    assert "case-b" in pending_files[0].name


# ---------- Branch 4 (ReEvaluateItem) ----------


def test_tick_reevaluate_item_runs_only_targeted_item(
    project: Path, write_intent, write_current_for, patch_providers, monkeypatch
):
    patch_providers({
        "pytest": FakeProvider("pytest", target_met("42ms")),
    })
    write_intent(
        "alpha",
        evidence=[
            {
                "id": "target-x",
                "type": "target",
                "provider": "pytest",
                "query": "m",
                "expect": "<50ms",
                "effort": "medium",
                "window": "5m",
            }
        ],
        version=1,
    )
    long_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    write_current_for(
        "alpha",
        {
            "target-x": {
                "verdict": "met",
                "attempts_used": 0,
                "last_observed": long_ago,
            }
        },
        intent_version=1,
    )
    monkeypatch.setattr("i2e_core.orchestrator.render", lambda root: None)
    result = tick(project)
    assert isinstance(result.action, ReEvaluateItem)
    assert result.action.item_id == "target-x"
    assert any(a.startswith("ran_evidence: alpha") for a in result.actions_log)


# ---------- Preflight failure ----------


def test_tick_preflight_failure_raises(
    project: Path, write_intent, patch_providers
):
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    # Active intent referencing an uninstalled provider.
    write_intent(
        "bad",
        evidence=[
            {
                "id": "x",
                "type": "case",
                "provider": "ghost",
                "query": "q",
                "expect": "p",
                "effort": "medium",
            }
        ],
        version=1,
    )
    with pytest.raises(PreflightFailed):
        tick(project)


# ---------- Tick-log content ----------


def test_tick_log_persists_actions(
    project: Path, write_intent, patch_providers, monkeypatch
):
    """The on-disk tick log file must reflect ``actions_log``."""
    import yaml
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent("alpha", evidence=_basic_evidence(), version=1)
    monkeypatch.setattr("i2e_core.orchestrator.render", lambda root: None)
    result = tick(project)
    files = list(logs_dir(project).glob("*-tick.yaml"))
    assert len(files) == 1
    data = yaml.safe_load(files[0].read_text(encoding="utf-8"))
    assert data["tick_id"] == result.tick_id
    assert data["actions"] == result.actions_log


# ---------- Evidence runner failure tolerance ----------


def test_tick_evidence_failure_records_but_does_not_raise(
    project: Path, write_intent, patch_providers, monkeypatch
):
    """If ``evidence_runner.run`` raises (e.g. an unexpected exception), the
    tick records the failure in ``actions_log`` and still returns."""
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent("alpha", evidence=_basic_evidence(), version=1)

    def boom(*args, **kwargs):
        raise RuntimeError("evidence runner exploded")

    monkeypatch.setattr("i2e_core.orchestrator.evidence_runner.run", boom)
    monkeypatch.setattr("i2e_core.orchestrator.render", lambda root: None)
    result = tick(project)
    assert isinstance(result.action, DevelopAndEvidence)
    assert any(
        "failed: evidence runner exploded" in a for a in result.actions_log
    )
