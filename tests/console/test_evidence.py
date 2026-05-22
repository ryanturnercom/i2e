"""Evidence view — catalogue (default) + Runs tab."""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path

from i2e_core.console.views.evidence import (
    render_evidence_catalogue,
    render_evidence_runs,
)
from i2e_core.intent import Capability, Constraint, EvidenceItem, Frontmatter, write_intent


def _make_intent(root: Path, slug: str) -> Path:
    intents = root / ".i2e" / "intents"
    intents.mkdir(parents=True, exist_ok=True)
    today = date.today()
    cap = Capability(
        frontmatter=Frontmatter(
            capability=slug,
            created=today,
            updated=today,
            version=1,
            status="active",
            watcher="@me",
        ),
        description="x",
        evidence=[
            EvidenceItem(
                id=f"{slug}-case",
                type="case",
                provider="pytest",
                query=f"tests/test_{slug}.py::test_x",
                expect="passes",
            ),
            EvidenceItem(
                id=f"{slug}-target",
                type="target",
                provider="human",
                query="Do the right thing?",
                expect="yes",
            ),
        ],
        constraints=[
            Constraint(
                id=f"{slug}-constraint",
                provider="pytest",
                query=f"tests/test_{slug}.py::test_constraint",
                expect="passes",
            )
        ],
    )
    return write_intent(cap, intents / f"{slug}.md")


def test_catalogue_renders_all_items(tmp_path):
    _make_intent(tmp_path, "cap-a")
    _make_intent(tmp_path, "cap-b")

    html = render_evidence_catalogue(tmp_path)
    # The catalogue is the default tab.
    assert 'data-tab="catalogue"' in html
    # Every item from every capability renders, including constraints.
    assert "cap-a-case" in html
    assert "cap-a-target" in html
    assert "cap-a-constraint" in html
    assert "cap-b-case" in html
    assert "cap-b-target" in html
    assert "cap-b-constraint" in html
    # Constraint rows carry type=constraint, not type=case.
    assert 'data-item-id="cap-a-constraint"' in html
    assert 'data-type="constraint"' in html


def test_runs_tab_chronological(tmp_path):
    # Seed two evidence runs at different mtimes so order is deterministic.
    cap_dir = tmp_path / ".i2e" / "evidence" / "demo-cap" / "runs"
    cap_dir.mkdir(parents=True)
    older = cap_dir / "2026-05-20-aaaaaa.yaml"
    older.write_text("ok\n")
    time.sleep(0.05)
    newer = cap_dir / "2026-05-21-bbbbbb.yaml"
    newer.write_text("ok\n")

    html = render_evidence_runs(tmp_path)

    assert 'data-tab="runs"' in html
    # Newer run appears before older in the rendered output.
    newer_idx = html.find("2026-05-21-bbbbbb")
    older_idx = html.find("2026-05-20-aaaaaa")
    assert newer_idx >= 0 and older_idx >= 0
    assert newer_idx < older_idx
