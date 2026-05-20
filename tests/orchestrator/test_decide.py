"""Tests for :func:`i2e_core.orchestrator.decide` — one per branch, plus precedence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from i2e_core.orchestrator import (
    AdaptThenRetry,
    ApplyResolutions,
    DevelopAndEvidence,
    ReEvaluateItem,
    Shippable,
    decide,
    parse_window,
)
from i2e_core.pending import PendingFile, write_pending

from .conftest import FakeProvider, always_pass


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


# ---------- parse_window ----------


def test_parse_window_minutes_hours_days_weeks():
    assert parse_window("5m") == timedelta(minutes=5)
    assert parse_window("2h") == timedelta(hours=2)
    assert parse_window("7d") == timedelta(days=7)
    assert parse_window("4w") == timedelta(weeks=4)
    # Whitespace tolerated.
    assert parse_window("  10 m ") == timedelta(minutes=10)


def test_parse_window_rejects_bad_input():
    for bad in ("", "30s", "5", "abc", "5q"):
        with pytest.raises(ValueError):
            parse_window(bad)
    with pytest.raises(ValueError):
        parse_window(None)  # type: ignore[arg-type]


# ---------- Branch 5: Shippable ----------


def test_decide_shippable_when_nothing_to_do(project: Path):
    """No intents, no pending — Shippable."""
    act = decide(project)
    assert isinstance(act, Shippable)


def test_decide_shippable_when_all_green(
    project: Path, write_intent, write_current_for, patch_providers
):
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent("alpha", evidence=_basic_evidence(), version=1)
    write_current_for(
        "alpha",
        {"case-a": {"verdict": "pass", "attempts_used": 0}},
        intent_version=1,
    )
    act = decide(project)
    assert isinstance(act, Shippable)


# ---------- Branch 2: DevelopAndEvidence ----------


def test_decide_develop_when_no_current_yaml(
    project: Path, write_intent, patch_providers
):
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent("alpha", evidence=_basic_evidence(), version=1)
    act = decide(project)
    assert isinstance(act, DevelopAndEvidence)
    assert act.capability == "alpha"


def test_decide_develop_picks_alphabetical_first(
    project: Path, write_intent, patch_providers
):
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent("bravo", evidence=_basic_evidence(), version=1)
    write_intent("alpha", evidence=_basic_evidence(), version=1)
    act = decide(project)
    assert isinstance(act, DevelopAndEvidence)
    assert act.capability == "alpha"


def test_decide_develop_when_intent_version_bumped(
    project: Path, write_intent, write_current_for, patch_providers
):
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    # Intent v2, but current.yaml says v1 → develop again.
    write_intent("alpha", evidence=_basic_evidence(), version=2)
    write_current_for(
        "alpha",
        {"case-a": {"verdict": "pass", "attempts_used": 0}},
        intent_version=1,
    )
    act = decide(project)
    assert isinstance(act, DevelopAndEvidence)


# ---------- Branch 3: AdaptThenRetry ----------


def test_decide_adapt_when_retry_budget_remaining(
    project: Path, write_intent, write_current_for, patch_providers
):
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent("alpha", evidence=_basic_evidence(), version=1)
    # medium case → max=6. attempts_used=2 ⇒ retry remaining.
    write_current_for(
        "alpha",
        {"case-a": {"verdict": "fail", "attempts_used": 2}},
        intent_version=1,
    )
    act = decide(project)
    assert isinstance(act, AdaptThenRetry)
    assert act.capability == "alpha"


# ---------- Branch 4: ReEvaluateItem ----------


def test_decide_reevaluate_when_window_elapsed(
    project: Path, write_intent, write_current_for, patch_providers
):
    """A target with verdict in {met,unmet,trending} and last_observed older
    than its window must trigger a single-item re-evaluation."""
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent(
        "alpha",
        evidence=[
            {
                "id": "target-x",
                "type": "target",
                "provider": "pytest",  # any installed provider — we never invoke it here
                "query": "metric",
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
    act = decide(project)
    assert isinstance(act, ReEvaluateItem)
    assert act.capability == "alpha"
    assert act.item_id == "target-x"


def test_decide_no_reevaluate_within_window(
    project: Path, write_intent, write_current_for, patch_providers
):
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent(
        "alpha",
        evidence=[
            {
                "id": "target-x",
                "type": "target",
                "provider": "pytest",
                "query": "metric",
                "expect": "<50ms",
                "effort": "medium",
                "window": "1h",
            }
        ],
        version=1,
    )
    fresh = datetime.now(timezone.utc) - timedelta(minutes=1)
    write_current_for(
        "alpha",
        {
            "target-x": {
                "verdict": "met",
                "attempts_used": 0,
                "last_observed": fresh,
            }
        },
        intent_version=1,
    )
    act = decide(project)
    assert isinstance(act, Shippable)


def test_decide_skips_item_without_window(
    project: Path, write_intent, write_current_for, patch_providers
):
    """Items lacking ``window:`` are not eligible for branch 4."""
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent(
        "alpha",
        evidence=[
            {
                "id": "case-a",
                "type": "case",
                "provider": "pytest",
                "query": "q",
                "expect": "passes",
                "effort": "medium",
            }
        ],
        version=1,
    )
    long_ago = datetime.now(timezone.utc) - timedelta(days=999)
    write_current_for(
        "alpha",
        {
            "case-a": {
                "verdict": "met",
                "attempts_used": 0,
                "last_observed": long_ago,
            }
        },
        intent_version=1,
    )
    act = decide(project)
    assert isinstance(act, Shippable)


def test_decide_skips_item_without_last_observed(
    project: Path, write_intent, write_current_for, patch_providers
):
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
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
    write_current_for(
        "alpha",
        {
            "target-x": {
                "verdict": "met",
                "attempts_used": 0,
                "last_observed": None,
            }
        },
        intent_version=1,
    )
    act = decide(project)
    assert isinstance(act, Shippable)


# ---------- Branch 1: ApplyResolutions ----------


def _resolved_pending(project: Path, capability: str = "alpha") -> Path:
    pf = PendingFile(
        status="resolved",
        kind="human_evaluation",
        capability=capability,
        item_id="case-a",
        asked_at=datetime.now(timezone.utc),
        ask="ok?",
        resolution="yes",
    )
    return write_pending(project, pf)


def test_decide_apply_resolutions_when_pending_resolved(
    project: Path, write_intent, patch_providers
):
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent("alpha", evidence=_basic_evidence(), version=1)
    _resolved_pending(project)
    act = decide(project)
    assert isinstance(act, ApplyResolutions)


# ---------- Precedence ----------


def test_branch_1_beats_branch_2(
    project: Path, write_intent, patch_providers
):
    """A resolved pending file must win even when develop is also needed."""
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    # Branch 2 would fire (no current.yaml), but branch 1 has a resolved file.
    write_intent("alpha", evidence=_basic_evidence(), version=1)
    _resolved_pending(project)
    act = decide(project)
    assert isinstance(act, ApplyResolutions)


def test_branch_2_beats_branch_3(
    project: Path, write_intent, write_current_for, patch_providers
):
    """Stale develop wins over adapt-retry."""
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent("alpha", evidence=_basic_evidence(), version=2)
    # Recorded version older than intent — develop needed; also failing item.
    write_current_for(
        "alpha",
        {"case-a": {"verdict": "fail", "attempts_used": 1}},
        intent_version=1,
    )
    act = decide(project)
    assert isinstance(act, DevelopAndEvidence)


def test_branch_3_beats_branch_4(
    project: Path, write_intent, write_current_for, patch_providers
):
    """Adapt-retry wins over a stale window."""
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent(
        "alpha",
        evidence=[
            {
                "id": "target-x",
                "type": "target",
                "provider": "pytest",
                "query": "m",
                "expect": "<50ms",
                "effort": "low",
                "window": "5m",
            }
        ],
        version=1,
    )
    # trending + budget remaining (low target → max=1, attempts_used=0).
    long_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    write_current_for(
        "alpha",
        {
            "target-x": {
                "verdict": "trending",
                "attempts_used": 0,
                "last_observed": long_ago,
            }
        },
        intent_version=1,
    )
    act = decide(project)
    assert isinstance(act, AdaptThenRetry)
