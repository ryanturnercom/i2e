"""HTML render tests — deep-link IDs and determinism."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from i2e_core.paths import report_path
from i2e_core.pending import PendingFile, write_pending
from i2e_core.report import render, render_to_string
from i2e_core.tick_log import TickLog, write_tick


def _basic_evidence() -> list[dict]:
    return [
        {
            "id": "case-a",
            "type": "case",
            "provider": "pytest",
            "query": "q",
            "expect": "passes",
            "effort": "medium",
        }
    ]


def test_render_writes_file(project: Path, write_intent, write_current_for) -> None:
    write_intent("alpha", evidence=_basic_evidence(), version=1)
    write_current_for(
        "alpha",
        {"case-a": {"verdict": "pass", "attempts_used": 0}},
        intent_version=1,
    )
    p = render(project)
    assert p == report_path(project)
    assert p.exists()
    text = p.read_text(encoding="utf-8")
    assert text.startswith("<!DOCTYPE html>")
    assert len(text) > 200


def test_render_contains_deep_link_ids(
    project: Path, write_intent, write_current_for
) -> None:
    write_intent("alpha", evidence=_basic_evidence(), version=1)
    write_current_for(
        "alpha",
        {"case-a": {"verdict": "pass", "attempts_used": 0}},
        intent_version=1,
    )
    # Open pending file.
    pf = PendingFile(
        status="open",
        kind="human_evaluation",
        capability="alpha",
        item_id="case-a",
        asked_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc),
        ask="Looks good?",
        verdict_options=["yes", "no"],
    )
    pending_path = write_pending(project, pf)

    # One tick log.
    tick = TickLog(
        tick_id="2026-05-19-abc123",
        ran_at=datetime(2026, 5, 19, 12, 30, 0, tzinfo=timezone.utc),
        actions=["ran_evidence: alpha (1/1 pass)"],
    )
    write_tick(project, tick)

    html = render_to_string(project)
    assert 'id="cap/alpha"' in html
    assert 'id="item/alpha/case-a"' in html
    assert f'id="pending/{pending_path.name}"' in html
    assert 'id="tick/2026-05-19-abc123"' in html


def test_render_is_deterministic(
    project: Path, write_intent, write_current_for
) -> None:
    """Same state → byte-identical output across consecutive renders."""
    write_intent("alpha", evidence=_basic_evidence(), version=1)
    write_current_for(
        "alpha",
        {"case-a": {"verdict": "pass", "attempts_used": 0}},
        intent_version=1,
    )
    # Add a tick so generated_at is anchored to its ran_at.
    write_tick(
        project,
        TickLog(
            tick_id="2026-05-19-abc123",
            ran_at=datetime(2026, 5, 19, 12, 30, 0, tzinfo=timezone.utc),
            actions=["ran_evidence: alpha"],
        ),
    )
    a = render(project).read_bytes()
    b = render(project).read_bytes()
    assert a == b


def test_render_shippable_pill_color(
    project: Path, write_intent, write_current_for
) -> None:
    write_intent("alpha", evidence=_basic_evidence(), version=1)
    write_current_for(
        "alpha",
        {"case-a": {"verdict": "pass", "attempts_used": 0}},
        intent_version=1,
    )
    html = render_to_string(project)
    assert "shippable green" in html
    # Now flip to failing.
    write_current_for(
        "alpha",
        {"case-a": {"verdict": "fail", "attempts_used": 1}},
        intent_version=1,
    )
    html = render_to_string(project)
    assert "shippable yellow" in html


def test_render_serve_url_banner(
    project: Path, write_intent, write_current_for
) -> None:
    write_intent("alpha", evidence=_basic_evidence(), version=1)
    write_current_for(
        "alpha",
        {"case-a": {"verdict": "pass", "attempts_used": 0}},
        intent_version=1,
    )
    serve_file = project / ".i2e" / ".serve.url"
    serve_file.write_text("http://127.0.0.1:54321/", encoding="utf-8")
    html = render_to_string(project)
    assert "Served via http://127.0.0.1:54321/" in html


def test_render_no_capabilities_message(project: Path) -> None:
    html = render_to_string(project)
    assert "No active capabilities yet." in html
