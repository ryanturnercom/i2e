"""Tests for :func:`i2e_core.adapt.escalate` + ``has_open_escalation``."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from i2e_core.adapt import escalate, has_open_escalation
from i2e_core.paths import pending_dir
from i2e_core.pending import read_pending
from i2e_core.tick_log import TickLog, write_tick


def _intent(write_intent):
    return write_intent(
        "shorten-url",
        evidence=[
            {
                "id": "usage-growth",
                "type": "target",
                "provider": "datadog",
                "query": "qoq",
                "expect": "+10%",
                "effort": "low",
            },
        ],
    )


def test_escalate_writes_well_formed_pending(
    project, write_intent, write_current_for
):
    _intent(write_intent)
    write_current_for(
        "shorten-url",
        {
            "usage-growth": {
                "verdict": "trending",
                "value": "+2.1% QoQ",
                "attempts_used": 1,
            },
        },
    )
    path = escalate(project, "shorten-url", "usage-growth")
    assert path.exists()
    pf = read_pending(path)
    assert pf.kind == "escalation"
    assert pf.status == "open"
    assert pf.capability == "shorten-url"
    assert pf.item_id == "usage-growth"
    assert pf.expect == "+10%"
    assert pf.observed == "+2.1% QoQ"
    assert "Pick one:" in pf.ask
    assert "Loosen the target" in pf.ask
    assert "Try a new approach" in pf.ask
    assert "Retire this target" in pf.ask
    assert "Accept current state" in pf.ask
    # Reason mentions the budget exhaustion.
    assert "max_attempts exhausted" in (pf.reason or "")
    # Attempts populated even with no run history → falls back to current.
    assert len(pf.attempts) >= 1


def test_escalate_includes_last_3_attempts_when_history_available(
    project, write_intent, write_current_for, write_run_for
):
    _intent(write_intent)
    # Four runs; only the last 3 should land in pf.attempts.
    run_ids = [
        "2026-04-01-aaa111",
        "2026-04-08-bbb222",
        "2026-04-15-ccc333",
        "2026-04-22-ddd444",
    ]
    for i, rid in enumerate(run_ids):
        write_run_for(
            "shorten-url",
            rid,
            {
                "usage-growth": {
                    "verdict": "trending",
                    "value": f"+{i + 1}.0%",
                    "attempts_used": i + 1,
                }
            },
        )
    write_current_for(
        "shorten-url",
        {
            "usage-growth": {
                "verdict": "trending",
                "value": "+4.0%",
                "attempts_used": 4,
            }
        },
        last_run=run_ids[-1],
    )

    # Tick logs so changes_since has something to give.
    for rid, msg in zip(
        run_ids[-3:],
        [
            "added share-to-twitter button",
            "prominent CTA on homepage",
            "reduced redirect latency",
        ],
    ):
        write_tick(
            project,
            TickLog(
                tick_id=rid,
                ran_at=datetime.now(timezone.utc),
                actions=[f"applied_change: shorten-url / usage-growth — {msg}"],
            ),
        )

    path = escalate(project, "shorten-url", "usage-growth")
    pf = read_pending(path)
    # Newest first, capped at 3.
    assert len(pf.attempts) == 3
    seen_run_ids = [a["run_id"] for a in pf.attempts]
    assert seen_run_ids == list(reversed(run_ids))[:3]
    # Each attempt has an observed value + a non-empty "changed" string.
    for a in pf.attempts:
        assert a["observed"]
        assert a["changed"]
        # tick log was present → changed should not be the placeholder
        assert a["changed"] != "(no tick log)"


def test_escalate_falls_back_when_no_tick_log(
    project, write_intent, write_current_for, write_run_for
):
    _intent(write_intent)
    write_run_for(
        "shorten-url",
        "2026-05-01-aaa111",
        {"usage-growth": {"verdict": "trending", "value": "+1%"}},
    )
    write_current_for(
        "shorten-url",
        {
            "usage-growth": {
                "verdict": "trending",
                "value": "+1%",
                "attempts_used": 1,
            }
        },
        last_run="2026-05-01-aaa111",
    )
    pf = read_pending(escalate(project, "shorten-url", "usage-growth"))
    assert pf.attempts[0]["changed"] == "(no tick log)"


def test_escalate_second_call_raises_file_exists(
    project, write_intent, write_current_for
):
    _intent(write_intent)
    write_current_for(
        "shorten-url",
        {
            "usage-growth": {
                "verdict": "unmet",
                "value": "+1%",
                "attempts_used": 1,
            }
        },
    )
    escalate(project, "shorten-url", "usage-growth")
    with pytest.raises(FileExistsError):
        escalate(project, "shorten-url", "usage-growth")


def test_has_open_escalation_detects_pending(
    project, write_intent, write_current_for
):
    _intent(write_intent)
    write_current_for(
        "shorten-url",
        {
            "usage-growth": {
                "verdict": "unmet",
                "value": "+1%",
                "attempts_used": 1,
            }
        },
    )
    assert has_open_escalation(project, "shorten-url", "usage-growth") is False
    escalate(project, "shorten-url", "usage-growth")
    assert has_open_escalation(project, "shorten-url", "usage-growth") is True


def test_escalate_unknown_item_raises(project, write_intent, write_current_for):
    _intent(write_intent)
    write_current_for(
        "shorten-url",
        {"usage-growth": {"verdict": "fail", "attempts_used": 1}},
    )
    with pytest.raises(KeyError):
        escalate(project, "shorten-url", "does-not-exist")


def test_escalate_requires_current(project, write_intent):
    _intent(write_intent)
    with pytest.raises(FileNotFoundError):
        escalate(project, "shorten-url", "usage-growth")
