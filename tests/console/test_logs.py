"""Logs view — timeline (default) and table modes."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from i2e_core.console.views.logs import render_logs
from i2e_core.tick_log import TickLog, write_tick


def _seed_tick(root: Path, tick_id: str, actions: list[str]) -> None:
    (root / ".i2e" / "logs").mkdir(parents=True, exist_ok=True)
    write_tick(
        root,
        TickLog(
            tick_id=tick_id,
            ran_at=datetime.now(timezone.utc),
            actions=actions,
        ),
    )


def test_timeline_default(tmp_path):
    _seed_tick(tmp_path, "2026-05-21-aaaaaa", ["ran_develop: foo"])
    _seed_tick(tmp_path, "2026-05-21-bbbbbb", ["ran_evidence: foo (3 pass)"])

    html = render_logs(tmp_path)

    assert 'data-mode="timeline"' in html
    assert '<ol class="timeline">' in html
    assert "2026-05-21-aaaaaa" in html
    assert "2026-05-21-bbbbbb" in html


def test_table_toggle(tmp_path):
    _seed_tick(tmp_path, "2026-05-21-aaaaaa", ["ran_develop: foo"])

    html = render_logs(tmp_path, mode="table")

    assert 'data-mode="table"' in html
    assert "<table" in html
    assert "<thead>" in html
    assert "2026-05-21-aaaaaa" in html
