"""Tests for the version-bump + items-signature logic."""

from __future__ import annotations

from pathlib import Path

from i2e_core import intent, intent_authoring
from i2e_core.intent import diff_summary, items_signature
from i2e_core.intent_template import default_capability


def _ev(item_id: str, **overrides) -> intent.EvidenceItem:
    data = dict(
        id=item_id, type="case", provider="pytest",
        query=f"tests/test_{item_id}.py", expect="passes", effort="medium",
    )
    data.update(overrides)
    return intent.EvidenceItem.model_validate(data)


def _cn(item_id: str, **overrides) -> intent.Constraint:
    data = dict(
        id=item_id, provider="pytest",
        query=f"tests/test_{item_id}.py", expect="passes", effort="medium",
    )
    data.update(overrides)
    return intent.Constraint.model_validate(data)


def test_signature_stable_under_reorder() -> None:
    cap_a = default_capability("x", "@me")
    cap_a = intent_authoring.upsert_evidence(cap_a, _ev("alpha"))
    cap_a = intent_authoring.upsert_evidence(cap_a, _ev("beta"))

    cap_b = default_capability("x", "@me")
    # Same set, different insertion order
    cap_b = intent_authoring.upsert_evidence(cap_b, _ev("beta"))
    cap_b = intent_authoring.upsert_evidence(cap_b, _ev("alpha"))

    assert items_signature(cap_a) == items_signature(cap_b)


def test_signature_changes_on_added_item() -> None:
    cap = default_capability("x", "@me")
    before = items_signature(cap)
    cap2 = intent_authoring.upsert_evidence(cap, _ev("added"))
    assert items_signature(cap2) != before


def test_signature_ignores_description_changes() -> None:
    cap = default_capability("x", "@me")
    before = items_signature(cap)
    cap2 = cap.model_copy(update={"description": "Completely different prose."})
    assert items_signature(cap2) == before


def test_signature_ignores_default_field_restatement() -> None:
    """Restating an effort default shouldn't count as material."""
    cap = default_capability("x", "@me")
    seed = cap.evidence[0]
    # Restate the same item, same query, with explicit effort=medium (the default)
    same_with_default = intent.EvidenceItem(
        id=seed.id,
        type=seed.type,
        provider=seed.provider,
        query=seed.query,
        expect=seed.expect,
        effort="medium",
    )
    cap2 = intent_authoring.upsert_evidence(cap, same_with_default)
    assert items_signature(cap2) == items_signature(cap)


def test_save_no_bump_on_description_only(
    project_root: Path, fake_skills_root: Path
) -> None:
    cap = default_capability("desc-only", "@me")
    cap.frontmatter.version = 3
    intent_authoring.save(project_root, cap)
    # Re-load and edit description only
    loaded = intent_authoring.load_or_init(project_root, "desc-only")
    edited = loaded.model_copy(update={"description": "Brand new prose."})
    intent_authoring.save(project_root, edited)
    final = intent_authoring.load_or_init(project_root, "desc-only")
    assert final.frontmatter.version == 3


def test_save_bumps_on_added_item(
    project_root: Path, fake_skills_root: Path
) -> None:
    cap = default_capability("add", "@me")
    cap.frontmatter.version = 1
    intent_authoring.save(project_root, cap)

    loaded = intent_authoring.load_or_init(project_root, "add")
    edited = intent_authoring.upsert_evidence(loaded, _ev("brand-new"))
    intent_authoring.save(project_root, edited)
    final = intent_authoring.load_or_init(project_root, "add")
    assert final.frontmatter.version == 2


def test_save_bumps_on_removed_constraint(
    project_root: Path, fake_skills_root: Path
) -> None:
    cap = default_capability("rm-cn", "@me")
    cap = intent_authoring.upsert_constraint(cap, _cn("cn1"))
    intent_authoring.save(project_root, cap)
    saved = intent_authoring.load_or_init(project_root, "rm-cn")
    v0 = saved.frontmatter.version

    edited = intent_authoring.remove_item(saved, "cn1")
    intent_authoring.save(project_root, edited)
    final = intent_authoring.load_or_init(project_root, "rm-cn")
    assert final.frontmatter.version == v0 + 1


def test_save_no_bump_on_reorder(
    project_root: Path, fake_skills_root: Path
) -> None:
    cap = default_capability("reorder", "@me")
    cap = intent_authoring.upsert_evidence(cap, _ev("alpha"))
    cap = intent_authoring.upsert_evidence(cap, _ev("beta"))
    intent_authoring.save(project_root, cap)
    saved = intent_authoring.load_or_init(project_root, "reorder")
    v0 = saved.frontmatter.version

    # Reorder by removing & re-adding in a different order
    reorder = intent_authoring.remove_item(saved, "alpha")
    reorder = intent_authoring.remove_item(reorder, "beta")
    reorder = intent_authoring.upsert_evidence(reorder, _ev("beta"))
    reorder = intent_authoring.upsert_evidence(reorder, _ev("alpha"))
    intent_authoring.save(project_root, reorder)
    final = intent_authoring.load_or_init(project_root, "reorder")
    assert final.frontmatter.version == v0


def test_new_file_keeps_version_one(
    project_root: Path, fake_skills_root: Path
) -> None:
    cap = default_capability("fresh", "@me")
    assert cap.frontmatter.version == 1
    intent_authoring.save(project_root, cap)
    final = intent_authoring.load_or_init(project_root, "fresh")
    assert final.frontmatter.version == 1


def test_diff_summary_describes_added(
    project_root: Path, fake_skills_root: Path
) -> None:
    cap = default_capability("ds", "@me")
    new_cap = intent_authoring.upsert_evidence(cap, _ev("freshly-added"))
    text = diff_summary(cap, new_cap)
    assert "freshly-added" in text


def test_diff_summary_describes_removed() -> None:
    cap = default_capability("ds2", "@me")
    cap = intent_authoring.upsert_evidence(cap, _ev("alpha"))
    cap = intent_authoring.upsert_evidence(cap, _ev("beta"))
    pruned = intent_authoring.remove_item(cap, "alpha")
    text = diff_summary(cap, pruned)
    assert "Removed evidence" in text and "alpha" in text


def test_diff_summary_no_material_changes() -> None:
    cap = default_capability("ds3", "@me")
    text = diff_summary(cap, cap)
    assert "No material changes" in text


def test_diff_summary_description_only() -> None:
    cap = default_capability("ds4", "@me")
    edited = cap.model_copy(update={"description": "Different prose."})
    text = diff_summary(cap, edited)
    assert "Description-only" in text
