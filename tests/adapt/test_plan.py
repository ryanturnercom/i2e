"""Tests for :func:`i2e_core.adapt.plan`."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from i2e_core.adapt import plan
from i2e_core.pending import PendingFile, write_pending


def _basic_intent(write_intent):
    return write_intent(
        "shorten-url",
        evidence=[
            {
                "id": "code-generated",
                "type": "case",
                "provider": "pytest",
                "query": "tests/test_x.py::test_y",
                "expect": "passes",
                "effort": "medium",
            },
            {
                "id": "redirect-latency-p95",
                "type": "target",
                "provider": "datadog",
                "query": "redirect_latency{quantile=0.95}",
                "expect": "<50ms",
                "effort": "low",
            },
            {
                "id": "lazy-target",
                "type": "target",
                "provider": "human",
                "query": "brand feel",
                "expect": "yes",
                "effort": "lazy",
            },
        ],
        constraints=[
            {
                "id": "no-open-redirect",
                "provider": "pytest",
                "query": "tests/adv/test_redirect.py",
                "expect": "passes",
                "effort": "high",
            },
        ],
    )


def test_no_current_returns_empty_plan(project, write_intent):
    _basic_intent(write_intent)
    pl = plan(project, "shorten-url")
    assert pl.capability == "shorten-url"
    assert pl.retries == []
    assert pl.escalations == []
    assert pl.done == []


def test_all_pass_goes_to_done(project, write_intent, write_current_for):
    _basic_intent(write_intent)
    write_current_for(
        "shorten-url",
        {
            "code-generated": {"verdict": "pass", "attempts_used": 0},
            "redirect-latency-p95": {"verdict": "met", "attempts_used": 0},
            "lazy-target": {"verdict": "pass", "attempts_used": 0},
            "no-open-redirect": {"verdict": "pass", "attempts_used": 0},
        },
    )
    pl = plan(project, "shorten-url")
    assert pl.retries == []
    assert pl.escalations == []
    assert set(pl.done) == {
        "code-generated",
        "redirect-latency-p95",
        "lazy-target",
        "no-open-redirect",
    }


def test_lazy_item_escalates_on_first_failure(
    project, write_intent, write_current_for
):
    _basic_intent(write_intent)
    write_current_for(
        "shorten-url",
        {
            "lazy-target": {"verdict": "unmet", "attempts_used": 0},
        },
    )
    pl = plan(project, "shorten-url")
    assert pl.retries == []
    assert len(pl.escalations) == 1
    e = pl.escalations[0]
    assert e.item_id == "lazy-target"
    assert e.effort == "lazy"
    assert e.max_attempts == 0


def test_medium_case_below_budget_retries(
    project, write_intent, write_current_for
):
    _basic_intent(write_intent)
    write_current_for(
        "shorten-url",
        {
            # medium case → max=6
            "code-generated": {"verdict": "fail", "attempts_used": 5},
        },
    )
    pl = plan(project, "shorten-url")
    assert pl.escalations == []
    assert len(pl.retries) == 1
    b = pl.retries[0]
    assert b.attempts_used == 5
    assert b.max_attempts == 6


def test_medium_case_at_budget_escalates(
    project, write_intent, write_current_for
):
    _basic_intent(write_intent)
    write_current_for(
        "shorten-url",
        {
            "code-generated": {"verdict": "fail", "attempts_used": 6},
        },
    )
    pl = plan(project, "shorten-url")
    assert pl.retries == []
    assert len(pl.escalations) == 1
    assert pl.escalations[0].attempts_used == 6


def test_awaiting_human_lands_in_done(
    project, write_intent, write_current_for
):
    _basic_intent(write_intent)
    write_current_for(
        "shorten-url",
        {
            "code-generated": {"verdict": "awaiting_human", "attempts_used": 2},
        },
    )
    pl = plan(project, "shorten-url")
    assert pl.retries == []
    assert pl.escalations == []
    assert "code-generated" in pl.done


def test_low_target_below_and_at_budget(
    project, write_intent, write_current_for
):
    _basic_intent(write_intent)
    # low target → max_attempts = 1
    write_current_for(
        "shorten-url",
        {
            "redirect-latency-p95": {"verdict": "trending", "attempts_used": 0},
        },
    )
    pl = plan(project, "shorten-url")
    assert len(pl.retries) == 1
    assert pl.retries[0].max_attempts == 1

    write_current_for(
        "shorten-url",
        {
            "redirect-latency-p95": {"verdict": "trending", "attempts_used": 1},
        },
    )
    pl = plan(project, "shorten-url")
    assert len(pl.escalations) == 1


def test_high_constraint_uses_case_map(
    project, write_intent, write_current_for
):
    _basic_intent(write_intent)
    # high constraint borrows the case map → max=10
    write_current_for(
        "shorten-url",
        {
            "no-open-redirect": {"verdict": "fail", "attempts_used": 9},
        },
    )
    pl = plan(project, "shorten-url")
    assert len(pl.retries) == 1
    assert pl.retries[0].max_attempts == 10


def test_open_escalation_excludes_item_from_escalations(
    project, write_intent, write_current_for
):
    _basic_intent(write_intent)
    write_current_for(
        "shorten-url",
        {
            "code-generated": {"verdict": "fail", "attempts_used": 99},
        },
    )
    # Pre-seed an open pending file.
    pf = PendingFile(
        status="open",
        kind="escalation",
        capability="shorten-url",
        item_id="code-generated",
        escalated_at=datetime.now(timezone.utc),
        ask="pick one",
    )
    write_pending(project, pf)
    pl = plan(project, "shorten-url")
    assert all(e.item_id != "code-generated" for e in pl.escalations)
    assert "code-generated" in pl.done


def test_item_in_current_but_not_intent_goes_to_done(
    project, write_intent, write_current_for
):
    _basic_intent(write_intent)
    write_current_for(
        "shorten-url",
        {
            # not declared in the intent anymore
            "retired-item": {"verdict": "fail", "attempts_used": 1},
        },
    )
    pl = plan(project, "shorten-url")
    assert "retired-item" in pl.done
    assert pl.retries == []
    assert pl.escalations == []
