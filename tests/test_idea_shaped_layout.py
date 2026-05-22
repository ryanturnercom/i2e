"""IDEA-shaped layout — Intent → Develop → Evidence → Adapt as the dominant frame.

A reader should be able to point at any region of the page and name which
IDEA stage it represents.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from i2e_core.evidence import CurrentEvidence, ItemVerdict, write_current
from i2e_core.pending import PendingFile, write_pending
from i2e_core.report import render_to_string


def _intent(name: str, status: str = "active") -> str:
    return (
        f"---\n"
        f"capability: {name}\n"
        f"created: '2026-05-20'\n"
        f"updated: '2026-05-20'\n"
        f"version: 1\n"
        f"status: {status}\n"
        f"watcher: '@me'\n"
        f"---\n"
        f"\n"
        f"## Evidence of success\n"
        f"\n"
        f"- id: {name}-case\n"
        f"  type: case\n"
        f"  provider: pytest\n"
        f"  query: tests/x.py::y\n"
        f"  expect: passes\n"
        f"  effort: medium\n"
        f"\n"
        f"## Constraints\n"
    )


def _seed(root: Path) -> None:
    for sub in ("intents", "evidence", "pending", "logs", "context"):
        (root / ".i2e" / sub).mkdir(parents=True, exist_ok=True)
    (root / ".i2e" / "intents" / "alpha.md").write_text(
        _intent("alpha", "active"), encoding="utf-8"
    )
    (root / ".i2e" / "intents" / "wip.md").write_text(
        _intent("wip", "draft"), encoding="utf-8"
    )
    write_current(
        root,
        CurrentEvidence(
            capability="alpha",
            last_run="2026-05-20-aaa000",
            intent_version=1,
            items={
                "alpha-case": ItemVerdict(
                    verdict="pass",
                    attempts_used=0,
                    last_observed=datetime.now(timezone.utc),
                )
            },
        ),
    )
    write_pending(
        root,
        PendingFile(
            status="open",
            kind="human_evaluation",
            capability="alpha",
            item_id="alpha-case",
            asked_at=datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc),
            ask="Is this good?",
            verdict_options=["yes", "no"],
        ),
    )


def test_implemented(tmp_path: Path) -> None:
    _seed(tmp_path)
    html = render_to_string(tmp_path)

    # --- 1. IDEA nav strip lives at the top of <main> -----------------------
    assert 'class="idea-nav"' in html
    main_start = html.index("<main>")
    nav_pos = html.index('class="idea-nav"')
    assert nav_pos > main_start
    # The nav chips have anchor links to the four stage sections.
    assert 'href="#stage-intent"' in html
    assert 'href="#stage-develop"' in html
    assert 'href="#stage-evidence"' in html
    assert 'href="#stage-adapt"' in html

    # --- 2. Four stages render in IDEA order --------------------------------
    pos_intent = html.index('id="stage-intent"')
    pos_develop = html.index('id="stage-develop"')
    pos_evidence = html.index('id="stage-evidence"')
    pos_adapt = html.index('id="stage-adapt"')
    assert pos_intent < pos_develop < pos_evidence < pos_adapt

    # Each stage has a labelled heading so the reader can name it.
    assert ">Intent " in html or ">Intent<" in html
    assert ">Develop " in html or ">Develop<" in html
    assert ">Evidence " in html or ">Evidence<" in html
    assert ">Adapt " in html or ">Adapt<" in html

    # --- 3. Content lands under the right stage -----------------------------
    intent_block = html[pos_intent:pos_develop]
    develop_block = html[pos_develop:pos_evidence]
    evidence_block = html[pos_evidence:pos_adapt]
    adapt_block = html[pos_adapt:]

    # Intent owns capability + draft cards.
    assert 'id="cap/alpha"' in intent_block
    assert 'id="draft/wip"' in intent_block
    # Develop owns the live in-flight panel.
    assert 'id="live-status"' in develop_block
    # Evidence owns the verdict roll-up.
    assert "evidence-roll" in evidence_block
    assert "1 pass" in evidence_block  # the one passing case shows up
    # Adapt owns the pending queue + recent ticks heading.
    assert "Pending queue" in adapt_block
    assert "Recent ticks" in adapt_block

    # --- 4. The nav chips carry the IDEA letters in big circles -------------
    # The accessibility label and each chip's letter mark are both present.
    assert 'aria-label="IDEA loop"' in html
    for letter in ("I", "D", "E", "A"):
        assert f'class="idea-letter">{letter}<' in html
