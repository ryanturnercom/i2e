"""Sidebar grouped filter — intents list groups capabilities by status."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from i2e_core.console.views.sidebar import render_sidebar
from i2e_core.intent import Capability, EvidenceItem, Frontmatter, write_intent


def _make_intent(root: Path, slug: str, status: str) -> None:
    intents = root / ".i2e" / "intents"
    intents.mkdir(parents=True, exist_ok=True)
    today = date.today()
    cap = Capability(
        frontmatter=Frontmatter(
            capability=slug,
            created=today,
            updated=today,
            version=1,
            status=status,
            watcher="@me",
        ),
        description=f"Test {slug}",
        evidence=[
            EvidenceItem(
                id=f"{slug}-case",
                type="case",
                provider="pytest",
                query=f"tests/test_{slug}.py::test_x",
                expect="passes",
            )
        ],
    )
    write_intent(cap, intents / f"{slug}.md")


def test_grouped_filter(tmp_path):
    _make_intent(tmp_path, "alpha-cap", "active")
    _make_intent(tmp_path, "beta-cap", "shipped")
    _make_intent(tmp_path, "gamma-cap", "draft")
    _make_intent(tmp_path, "delta-cap", "retired")

    html = render_sidebar(tmp_path, mode="grouped")

    # Grouped mode emits a section per status. Section headers are
    # stable so htmx can target them.
    assert 'data-group="active"' in html
    assert 'data-group="draft"' in html
    assert 'data-group="shipped"' in html
    assert 'data-group="retired"' in html

    # Each slug must land under exactly one group (no duplicates).
    # Count distinct row entries — data-slug is unique per row even
    # though the slug also appears in the href and link text.
    for slug in ("alpha-cap", "beta-cap", "gamma-cap", "delta-cap"):
        assert html.count(f'data-slug="{slug}"') == 1
