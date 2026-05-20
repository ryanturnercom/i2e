"""Tests for `i2e_core.intent_authoring` (load/upsert/remove)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from i2e_core import intent, intent_authoring
from i2e_core.intent_template import default_capability


def _ev(item_id: str = "a", **overrides) -> intent.EvidenceItem:
    data = dict(
        id=item_id, type="case", provider="pytest",
        query="tests/test_x.py", expect="passes", effort="medium",
    )
    data.update(overrides)
    return intent.EvidenceItem.model_validate(data)


def _cn(item_id: str = "c", **overrides) -> intent.Constraint:
    data = dict(
        id=item_id, provider="pytest",
        query="tests/test_c.py", expect="passes", effort="medium",
    )
    data.update(overrides)
    return intent.Constraint.model_validate(data)


def test_load_or_init_returns_scaffold_for_missing(project_root: Path) -> None:
    cap = intent_authoring.load_or_init(project_root, "brand-new")
    assert cap.frontmatter.capability == "brand-new"
    assert cap.frontmatter.version == 1
    assert cap.frontmatter.status == "draft"
    assert len(cap.evidence) >= 1
    assert cap.evidence[0].provider == "pytest"


def test_load_or_init_returns_existing(project_root: Path) -> None:
    cap = default_capability("existing", "@me")
    target = intent_authoring.intent_path(project_root, "existing")
    intent.write_intent(cap, target)

    loaded = intent_authoring.load_or_init(project_root, "existing")
    assert loaded.frontmatter.capability == "existing"
    assert loaded.evidence[0].id == cap.evidence[0].id


def test_upsert_evidence_replaces_by_id(project_root: Path) -> None:
    cap = default_capability("x", "@me")
    original_id = cap.evidence[0].id
    new_item = _ev(item_id=original_id, query="tests/test_changed.py")
    updated = intent_authoring.upsert_evidence(cap, new_item)
    # Same number of items
    assert len(updated.evidence) == len(cap.evidence)
    # And the replacement actually happened
    [match] = [it for it in updated.evidence if it.id == original_id]
    assert match.query == "tests/test_changed.py"


def test_upsert_evidence_appends_new() -> None:
    cap = default_capability("x", "@me")
    new = _ev(item_id="another-case")
    updated = intent_authoring.upsert_evidence(cap, new)
    ids = [it.id for it in updated.evidence]
    assert "another-case" in ids
    assert len(ids) == len(cap.evidence) + 1


def test_upsert_constraint_replaces_by_id() -> None:
    cap = default_capability("x", "@me")
    cap = intent_authoring.upsert_constraint(cap, _cn(item_id="cn1"))
    cap = intent_authoring.upsert_constraint(
        cap, _cn(item_id="cn1", query="tests/test_replaced.py")
    )
    assert len(cap.constraints) == 1
    assert cap.constraints[0].query == "tests/test_replaced.py"


def test_remove_item_evidence() -> None:
    cap = default_capability("x", "@me")
    cap = intent_authoring.upsert_evidence(cap, _ev(item_id="extra"))
    pruned = intent_authoring.remove_item(cap, "extra")
    assert all(it.id != "extra" for it in pruned.evidence)


def test_remove_item_constraint() -> None:
    cap = default_capability("x", "@me")
    cap = intent_authoring.upsert_constraint(cap, _cn(item_id="cn-x"))
    pruned = intent_authoring.remove_item(cap, "cn-x")
    assert all(it.id != "cn-x" for it in pruned.constraints)


def test_remove_item_idempotent_when_missing() -> None:
    cap = default_capability("x", "@me")
    before = len(cap.evidence)
    pruned = intent_authoring.remove_item(cap, "does-not-exist")
    assert len(pruned.evidence) == before
    assert len(pruned.constraints) == 0


def test_default_capability_passes_validation() -> None:
    """The scaffold itself must satisfy the forced-evidence rules."""
    from i2e_core import validator

    cap = default_capability("foo", "@me")
    validator.validate_capability(cap, installed_providers={"pytest"})


def test_default_capability_dates_are_today(monkeypatch) -> None:
    from i2e_core import intent_template

    fixed = date(2026, 5, 19)
    monkeypatch.setattr(intent_template, "today_utc", lambda: fixed)
    cap = intent_template.default_capability("foo", "@me")
    assert cap.frontmatter.created == fixed
    assert cap.frontmatter.updated == fixed
