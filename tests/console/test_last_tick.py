"""Static report.html shrinks to a last-tick summary.

i2e-report now renders only the most recent tick's actions + an empty
state when no ticks exist yet. The rich UI lives in the console.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from i2e_core.report.last_tick import render_last_tick
from i2e_core.tick_log import TickLog, write_tick


def _bootstrap(root: Path) -> None:
    (root / ".i2e" / "logs").mkdir(parents=True)


def test_renders_when_no_ticks(tmp_path):
    _bootstrap(tmp_path)
    html = render_last_tick(tmp_path)
    assert "<html" in html.lower()
    assert "No ticks yet" in html


def test_renders_summary_of_latest(tmp_path):
    _bootstrap(tmp_path)
    tl = TickLog(
        tick_id="2026-05-21-abc123",
        ran_at=datetime(2026, 5, 21, 14, 23, 0, tzinfo=timezone.utc),
        actions=[
            "ran_develop: capability-foo (LLM-driven; subprocess hook deferred)",
            "ran_evidence: capability-foo (3 pass, 0 trending, 0 fail)",
            "promoted_to_shipped: capability-foo",
        ],
    )
    write_tick(tmp_path, tl)

    html = render_last_tick(tmp_path)
    assert "2026-05-21-abc123" in html
    assert "capability-foo" in html
    # Each action gets surfaced.
    assert "ran_develop" in html
    assert "ran_evidence" in html
    assert "promoted_to_shipped" in html
