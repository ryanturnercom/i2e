"""Tests for :mod:`i2e_core.tick_log`."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from i2e_core.tick_log import (
    TickLog,
    changes_since,
    latest_tick_for,
    write_tick,
)


def test_empty_actions_writes_nothing(project):
    tick = TickLog(
        tick_id="2026-05-19-aaa111",
        ran_at=datetime.now(timezone.utc),
        actions=[],
    )
    result = write_tick(project, tick)
    assert result is None
    assert list((project / ".i2e" / "logs").iterdir()) == []


def test_non_empty_tick_written_and_immutable(project):
    tick = TickLog(
        tick_id="2026-05-19-aaa111",
        ran_at=datetime.now(timezone.utc),
        actions=["ran_develop: shorten-url (intent v1 -> v2)"],
    )
    p = write_tick(project, tick)
    assert p is not None
    assert p.exists()
    assert p.name == "2026-05-19-aaa111-tick.yaml"

    with pytest.raises(FileExistsError):
        write_tick(project, tick)


def test_latest_tick_for_returns_newest_match(project):
    ticks = [
        TickLog(
            tick_id="2026-05-19-aaa111",
            ran_at=datetime.now(timezone.utc),
            actions=["ran_develop: shorten-url (intent v1 -> v2)"],
        ),
        TickLog(
            tick_id="2026-05-19-bbb222",
            ran_at=datetime.now(timezone.utc),
            actions=["ran_evidence: other-cap (1 pass)"],
        ),
        TickLog(
            tick_id="2026-05-19-ccc333",
            ran_at=datetime.now(timezone.utc),
            actions=["ran_adapt: shorten-url (retries=2, escalations=1)"],
        ),
    ]
    for t in ticks:
        write_tick(project, t)
        # Bump mtime so newest-by-mtime ordering is deterministic.
        time.sleep(0.02)
    # Force ordering: rewrite mtimes ascending.
    for i, t in enumerate(ticks):
        p = project / ".i2e" / "logs" / f"{t.tick_id}-tick.yaml"
        mtime = 1_700_000_000 + i * 60
        os.utime(p, (mtime, mtime))

    latest = latest_tick_for(project, "shorten-url")
    assert latest is not None
    assert latest.tick_id == "2026-05-19-ccc333"


def test_latest_tick_for_with_item_id_filter(project):
    ticks = [
        TickLog(
            tick_id="2026-05-19-aaa111",
            ran_at=datetime.now(timezone.utc),
            actions=[
                "applied_resolution: shorten-url / usage-growth",
            ],
        ),
        TickLog(
            tick_id="2026-05-19-bbb222",
            ran_at=datetime.now(timezone.utc),
            actions=["ran_evidence: shorten-url (1 trending)"],
        ),
    ]
    for t in ticks:
        write_tick(project, t)
    for i, t in enumerate(ticks):
        p = project / ".i2e" / "logs" / f"{t.tick_id}-tick.yaml"
        mtime = 1_700_000_000 + i * 60
        os.utime(p, (mtime, mtime))

    latest = latest_tick_for(project, "shorten-url", "usage-growth")
    assert latest is not None
    assert latest.tick_id == "2026-05-19-aaa111"


def test_latest_tick_for_returns_none_when_no_match(project):
    write_tick(
        project,
        TickLog(
            tick_id="2026-05-19-aaa111",
            ran_at=datetime.now(timezone.utc),
            actions=["ran_develop: some-other-cap (intent v1 -> v2)"],
        ),
    )
    assert latest_tick_for(project, "shorten-url") is None
    assert latest_tick_for(project, "missing", "missing-item") is None


def test_changes_since_returns_last_n_newest_first(project):
    actions = [
        ("2026-05-01-aaa111", "applied_change: shorten-url / usage-growth — added share button"),
        ("2026-05-08-bbb222", "applied_change: shorten-url / usage-growth — homepage CTA"),
        ("2026-05-15-ccc333", "applied_change: shorten-url / usage-growth — faster redirect"),
        ("2026-05-22-ddd444", "applied_change: shorten-url / usage-growth — referral feature"),
    ]
    for i, (tid, action) in enumerate(actions):
        write_tick(
            project,
            TickLog(
                tick_id=tid,
                ran_at=datetime.now(timezone.utc),
                actions=[action],
            ),
        )
        p = project / ".i2e" / "logs" / f"{tid}-tick.yaml"
        mtime = 1_700_000_000 + i * 60
        os.utime(p, (mtime, mtime))

    out = changes_since(project, "shorten-url", "usage-growth", n=3)
    assert len(out) == 3
    # Newest first.
    assert out[0][0] == "2026-05-22-ddd444"
    assert out[1][0] == "2026-05-15-ccc333"
    assert out[2][0] == "2026-05-08-bbb222"
    # Capability + item id stripped from the descriptions.
    for _, desc in out:
        assert "shorten-url" not in desc
        assert "usage-growth" not in desc


def test_changes_since_returns_fewer_when_history_short(project):
    write_tick(
        project,
        TickLog(
            tick_id="2026-05-01-aaa111",
            ran_at=datetime.now(timezone.utc),
            actions=["applied_change: shorten-url / usage-growth — only one"],
        ),
    )
    out = changes_since(project, "shorten-url", "usage-growth", n=3)
    assert len(out) == 1


def test_changes_since_ignores_unrelated_ticks(project):
    write_tick(
        project,
        TickLog(
            tick_id="2026-05-01-aaa111",
            ran_at=datetime.now(timezone.utc),
            actions=["ran_develop: other-cap (intent v1 -> v2)"],
        ),
    )
    out = changes_since(project, "shorten-url", "usage-growth", n=3)
    assert out == []


def test_corrupt_tick_files_are_skipped(project):
    # Write one valid, one corrupt.
    write_tick(
        project,
        TickLog(
            tick_id="2026-05-19-aaa111",
            ran_at=datetime.now(timezone.utc),
            actions=["ran_develop: shorten-url (intent v1 -> v2)"],
        ),
    )
    corrupt = project / ".i2e" / "logs" / "2026-05-19-xxx999-tick.yaml"
    corrupt.write_text("not: [valid yaml", encoding="utf-8")
    # Should not raise.
    out = latest_tick_for(project, "shorten-url")
    assert out is not None and out.tick_id == "2026-05-19-aaa111"
