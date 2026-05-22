"""Intent detail view — split layout and Promote button wiring."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from i2e_core.console.views.intent import render_intent_detail
from i2e_core.intent import Capability, EvidenceItem, Frontmatter, write_intent


def _make_draft(root: Path, slug: str = "demo-cap") -> None:
    intents = root / ".i2e" / "intents"
    intents.mkdir(parents=True, exist_ok=True)
    today = date.today()
    cap = Capability(
        frontmatter=Frontmatter(
            capability=slug,
            created=today,
            updated=today,
            version=1,
            status="draft",
            watcher="@me",
        ),
        description="demo",
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


def test_renders_split_layout(tmp_path):
    _make_draft(tmp_path, "demo-cap")
    html = render_intent_detail(tmp_path, "demo-cap")
    # Split layout = #primary on the left, #meta (sticky) on the right.
    assert 'id="primary"' in html
    assert 'id="meta"' in html
    assert 'class="split"' in html or 'data-slug="demo-cap"' in html
    # Evidence table must render even with no evidence runs yet.
    assert 'id="evidence-table"' in html
    assert 'demo-cap-case' in html
    # Raw source viewer is read-only with a footer hint.
    assert "Edit via i2e-intent" in html or "edit via i2e-intent" in html.lower()


def test_promote_button_validates(tmp_path):
    _make_draft(tmp_path, "demo-cap")
    html = render_intent_detail(tmp_path, "demo-cap")
    # The Promote button must POST to the promote endpoint and be
    # enabled for a draft (validation runs server-side on click).
    assert 'id="promote-button"' in html
    assert 'hx-post="/api/intents/demo-cap/promote"' in html
    # On a draft, the button must not carry the disabled attribute.
    button_idx = html.find('id="promote-button"')
    # Inspect the substring covering the <button> element.
    btn_end = html.find(">", button_idx)
    button_open = html[button_idx:btn_end]
    assert "disabled" not in button_open
