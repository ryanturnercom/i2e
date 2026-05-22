"""Console resolve action — writes resolution block, visible to i2e-adapt."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from i2e_core.console.actions.resolve import resolve
from i2e_core.pending import (
    PendingFile,
    list_resolved_pending,
    read_pending,
    write_pending,
)


def _make_open_pending(root: Path) -> Path:
    pf = PendingFile(
        kind="human_evaluation",
        capability="demo-cap",
        item_id="demo-target",
        asked_at=datetime(2026, 5, 21, 14, 0, 0, tzinfo=timezone.utc),
        ask="Does the demo strip render?",
        expect="yes",
        verdict_options=["yes", "no", "partial"],
    )
    return write_pending(root, pf)


def test_resolve_writes_resolution_block(tmp_path):
    path = _make_open_pending(tmp_path)
    assert path.exists()
    assert read_pending(path).status == "open"

    resolve(tmp_path, path.name, verdict="yes", notes="Looks correct")

    updated = read_pending(path)
    assert updated.status == "resolved"
    assert updated.resolution is not None
    assert "yes" in updated.resolution
    assert "Looks correct" in updated.resolution


def test_resolve_visible_to_adapt_skill(tmp_path):
    path = _make_open_pending(tmp_path)
    # Before resolve: not in resolved list.
    assert path not in list_resolved_pending(tmp_path)

    resolve(tmp_path, path.name, verdict="yes")

    # After resolve: the adapt skill's discovery helper sees it.
    resolved = list_resolved_pending(tmp_path)
    assert path in resolved
