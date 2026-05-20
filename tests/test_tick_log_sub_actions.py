"""Tests for the tick-log-sub-actions slice (swarm-tick §5)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from i2e_core.tick_log import TickLog, _read_tick, latest_tick_for, write_tick


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / ".i2e" / "logs").mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_implemented(project: Path) -> None:
    """A batch tick records sub_actions per slug; legacy ticks stay clean."""
    # Batch tick: three slugs, one structured nested list each.
    batch_tick = TickLog(
        tick_id="2026-05-20-batch1",
        ran_at=datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc),
        actions=[
            "ran_develop: alpha (intent v1 -> v1)",
            "ran_develop: beta (intent v1 -> v1)",
            "ran_develop: gamma (intent v1 -> v1)",
        ],
        sub_actions=[
            [
                "ran_develop: alpha (intent v1 -> v1)",
                "ran_evidence: alpha (pass=2 total=2)",
            ],
            [
                "ran_develop: beta (intent v1 -> v1)",
                "ran_evidence: beta (pass=1 total=1)",
            ],
            [
                "ran_develop: gamma (intent v1 -> v1)",
                "ran_evidence: gamma (pass=4 total=4)",
            ],
        ],
    )
    path = write_tick(project, batch_tick)
    assert path is not None and path.exists()

    # Round-trip via the reader.
    reread = _read_tick(path)
    assert reread is not None
    assert reread.sub_actions == batch_tick.sub_actions
    assert reread.actions == batch_tick.actions

    # On-disk YAML carries the sub_actions key.
    on_disk = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "sub_actions" in on_disk
    assert len(on_disk["sub_actions"]) == 3

    # The existing latest_tick_for helper still finds slugs through actions.
    assert latest_tick_for(project, "alpha") is not None
    assert latest_tick_for(project, "beta") is not None

    # Legacy tick (no sub_actions): YAML must not gain a `sub_actions: null`
    # key — file shape stays byte-identical to pre-swarm tick logs.
    legacy = TickLog(
        tick_id="2026-05-20-legacy",
        ran_at=datetime(2026, 5, 20, 13, 0, 0, tzinfo=timezone.utc),
        actions=["ran_evidence: solo (pass=1 total=1)"],
    )
    legacy_path = write_tick(project, legacy)
    assert legacy_path is not None
    legacy_disk = yaml.safe_load(legacy_path.read_text(encoding="utf-8"))
    assert "sub_actions" not in legacy_disk
    # Legacy ticks still reread without error and report sub_actions=None.
    reread_legacy = _read_tick(legacy_path)
    assert reread_legacy is not None
    assert reread_legacy.sub_actions is None


def test_empty_actions_still_skips_write(project: Path) -> None:
    """Sub-action support must not break the empty-tick short-circuit."""
    t = TickLog(
        tick_id="2026-05-20-empty",
        ran_at=datetime.now(timezone.utc),
        actions=[],
        sub_actions=[],  # empty list is still "no actions"
    )
    assert write_tick(project, t) is None
