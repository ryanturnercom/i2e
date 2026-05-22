"""Workers view — claim.json fields + live log tail."""

from __future__ import annotations

import json
from pathlib import Path

from i2e_core.console.views.workers import render_workers


def _seed_worker(root: Path, slug: str, claim: dict, log_lines: list[str] | None = None) -> Path:
    wt = root / ".i2e" / "worktrees" / slug
    wt.mkdir(parents=True, exist_ok=True)
    (wt / "claim.json").write_text(json.dumps(claim), encoding="utf-8")
    if log_lines is not None:
        (wt / "log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    return wt


def test_renders_claim_json_fields(tmp_path):
    _seed_worker(
        tmp_path,
        "demo-cap",
        {
            "agent_id": "agent-99",
            "capability": "demo-cap",
            "step": "develop",
            "started_at": "2026-05-21T14:00:00Z",
            "progress": "writing tests",
        },
    )
    html = render_workers(tmp_path)
    assert "demo-cap" in html
    assert "agent-99" in html
    assert "develop" in html
    assert "writing tests" in html
    assert "2026-05-21T14:00:00Z" in html


def test_renders_live_log_tail(tmp_path):
    log_lines = [f"line {i}" for i in range(1, 11)]
    _seed_worker(
        tmp_path,
        "demo-cap",
        {
            "agent_id": "a",
            "capability": "demo-cap",
            "step": "develop",
            "started_at": "2026-05-21T14:00:00Z",
        },
        log_lines=log_lines,
    )
    html = render_workers(tmp_path)
    # Tail must include the most-recent line.
    assert "line 10" in html
    # And the log-tail container is structured for htmx targeting.
    assert 'data-strip="log-tail"' in html
