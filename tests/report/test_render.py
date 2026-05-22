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


def test_footer_links_to_ryanturner(project: Path) -> None:
    """The footer must reference ryanturner.com on every render, regardless of state."""
    # Empty project (no intents) — footer still renders.
    html = render_to_string(project)
    assert "<footer" in html
    assert 'href="https://ryanturner.com"' in html
    assert 'target="_blank"' in html
    assert 'rel="noopener"' in html
    assert "ryanturner.com" in html

    # And again with an active capability + drafts in play.
    from i2e_core.evidence import CurrentEvidence, ItemVerdict, write_current
    from datetime import datetime, timezone

    # Reuse the conftest write_intent indirectly via simple inline writes.
    intents = project / ".i2e" / "intents"
    intents.mkdir(parents=True, exist_ok=True)
    (intents / "alpha.md").write_text(
        "---\ncapability: alpha\ncreated: '2026-05-20'\nupdated: '2026-05-20'\n"
        "version: 1\nstatus: active\nwatcher: '@me'\n---\n\n"
        "## Evidence of success\n\n"
        "- id: case-a\n  type: case\n  provider: pytest\n  query: q\n"
        "  expect: passes\n  effort: medium\n\n## Constraints\n",
        encoding="utf-8",
    )
    write_current(
        project,
        CurrentEvidence(
            capability="alpha",
            last_run="2026-05-20-aaa000",
            intent_version=1,
            items={
                "case-a": ItemVerdict(
                    verdict="pass",
                    attempts_used=0,
                    last_observed=datetime.now(timezone.utc),
                )
            },
        ),
    )
    html2 = render_to_string(project)
    assert 'href="https://ryanturner.com"' in html2
    # Footer comes after </main> so it sits at the bottom of the page.
    assert html2.index("</main>") < html2.index("<footer")


def test_html_has_drafts_section(
    project: Path, write_intent, write_current_for
) -> None:
    write_intent("alpha", evidence=_basic_evidence(), version=1, status="active")
    write_current_for(
        "alpha",
        {"case-a": {"verdict": "pass", "attempts_used": 0}},
        intent_version=1,
    )
    write_intent(
        "wip-feature", evidence=_basic_evidence(), version=1, status="draft"
    )
    html = render_to_string(project)
    # Drafts heading and a draft-specific deep-link id should be present.
    assert "Drafts" in html
    assert 'id="draft/wip-feature"' in html
    # Active capability still appears under its own heading.
    assert 'id="cap/alpha"' in html
    # When there are no drafts, the section should not render.
    (project / ".i2e" / "intents" / "wip-feature.md").unlink()
    html2 = render_to_string(project)
    assert 'id="draft/wip-feature"' not in html2
