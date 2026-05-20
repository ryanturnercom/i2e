"""Tests for the ``i2e-spec`` decomposer + reconciler."""

from __future__ import annotations

from pathlib import Path

import pytest

from i2e_core import intent
from i2e_core.spec import (
    decompose,
    reconcile,
    save_decomposition,
)


SAMPLE_PRD = (
    Path(__file__).parent / "fixtures" / "specs" / "sample-prd.md"
)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    for sub in ("context", "intents", "evidence", "pending", "logs", "specs"):
        (tmp_path / ".i2e" / sub).mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_fixture_prd_produces_expected_intents() -> None:
    prd = SAMPLE_PRD.read_text(encoding="utf-8")
    caps = decompose(prd, slug="sample-prd")
    slugs = [c.frontmatter.capability for c in caps]
    assert slugs == ["shorten-links", "track-clicks", "expose-analytics"]
    # Each capability is a valid Capability with at least one evidence
    # item (rule 3) and a pytest provider stub.
    for c in caps:
        assert c.evidence
        assert c.evidence[0].provider == "pytest"


def test_original_spec_saved_under_dot_i2e_specs(project: Path) -> None:
    prd = SAMPLE_PRD.read_text(encoding="utf-8")
    written = save_decomposition(project, prd, slug="sample-prd")
    spec_file = project / ".i2e" / "specs" / "sample-prd.md"
    assert spec_file in written
    assert spec_file.read_text(encoding="utf-8") == prd


def test_each_intent_frontmatter_links_to_spec(project: Path) -> None:
    prd = SAMPLE_PRD.read_text(encoding="utf-8")
    save_decomposition(project, prd, slug="sample-prd")

    for slug, ref in [
        ("shorten-links", "1"),
        ("track-clicks", "2"),
        ("expose-analytics", "3"),
    ]:
        p = project / ".i2e" / "intents" / f"{slug}.md"
        cap = intent.parse_intent(p)
        assert cap.frontmatter.spec == "sample-prd"
        assert cap.frontmatter.spec_section == ref


def test_reconcile_proposes_edit_when_spec_section_changes(
    project: Path,
) -> None:
    prd = SAMPLE_PRD.read_text(encoding="utf-8")
    save_decomposition(project, prd, slug="sample-prd")

    # Edit the saved spec — change Section 2's body. The intent on disk
    # still reflects the original body, so reconcile must flag it.
    spec_file = project / ".i2e" / "specs" / "sample-prd.md"
    edited = spec_file.read_text(encoding="utf-8").replace(
        "increments a per-link\ncounter",
        "uses a sliding-window per-link counter",
    )
    spec_file.write_text(edited, encoding="utf-8")

    actions = reconcile(project, "sample-prd")
    edits = [a for a in actions if a.kind == "edit"]
    assert any(a.capability == "track-clicks" for a in edits)


def test_reconcile_proposes_add_and_retire_on_section_set_change(
    project: Path,
) -> None:
    prd = SAMPLE_PRD.read_text(encoding="utf-8")
    save_decomposition(project, prd, slug="sample-prd")

    # Replace Section 3 entirely with a new one; the old "expose-analytics"
    # must be proposed for retire, and "billing-events" for add.
    spec_file = project / ".i2e" / "specs" / "sample-prd.md"
    text = spec_file.read_text(encoding="utf-8")
    new_text = text.split("## Section 3:")[0] + (
        "## Section 3: Billing Events\n\n"
        "Each click writes a billing event for downstream invoicing.\n"
    )
    spec_file.write_text(new_text, encoding="utf-8")

    actions = reconcile(project, "sample-prd")
    kinds_by_cap = {a.capability: a.kind for a in actions}
    assert kinds_by_cap.get("expose-analytics") == "retire"
    assert kinds_by_cap.get("billing-events") == "add"


def test_decomposition_populates_depends_on_from_spec_order() -> None:
    prd = SAMPLE_PRD.read_text(encoding="utf-8")
    caps = decompose(prd, slug="sample-prd")
    # First capability has no parent; each subsequent capability depends
    # on its predecessor.
    assert caps[0].frontmatter.depends_on == []
    assert caps[1].frontmatter.depends_on == [caps[0].frontmatter.capability]
    assert caps[2].frontmatter.depends_on == [caps[1].frontmatter.capability]


def test_spec_doc_lists_i2e_spec_skill_in_appendix_b() -> None:
    spec = (
        Path(__file__).resolve().parent.parent
        / ".documentation"
        / "I2E_simplified.md"
    )
    text = spec.read_text(encoding="utf-8")
    appendix_b = text.split("## Appendix B")[1]
    assert "i2e-spec" in appendix_b


def test_all_decomposed_intents_have_status_draft() -> None:
    prd = SAMPLE_PRD.read_text(encoding="utf-8")
    caps = decompose(prd, slug="sample-prd")
    assert all(c.frontmatter.status == "draft" for c in caps)


def test_single_intent_workflow_still_works(project: Path) -> None:
    """The legacy one-capability-at-a-time path (``i2e-intent``) must keep
    working alongside the new bulk decomposer.
    """
    from i2e_core.intent_authoring import load_or_init, save

    cap = load_or_init(project, "manual-cap", "@me")
    cap = cap.model_copy(
        update={
            "evidence": [
                intent.EvidenceItem(
                    id="works",
                    type="case",
                    provider="pytest",
                    query="tests/test_manual.py::test_one",
                    expect="passes",
                    effort="medium",
                )
            ]
        }
    )
    path = save(project, cap)
    assert path.exists()
    reparsed = intent.parse_intent(path)
    assert reparsed.frontmatter.capability == "manual-cap"
    assert reparsed.evidence[0].id == "works"
