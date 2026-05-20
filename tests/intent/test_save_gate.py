"""Tests for the save-time validation gate."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from i2e_core import intent, intent_authoring, intent_save_gate, validator
from i2e_core.intent_template import default_capability


def _ev(item_id: str = "a", **overrides) -> intent.EvidenceItem:
    data = dict(
        id=item_id, type="case", provider="pytest",
        query="tests/test_x.py", expect="passes", effort="medium",
    )
    data.update(overrides)
    return intent.EvidenceItem.model_validate(data)


def test_unknown_provider_raises(project_root: Path, fake_skills_root: Path) -> None:
    cap = default_capability("u-prov", "@me")
    cap = intent_authoring.upsert_evidence(
        cap, _ev(item_id="bogus", provider="datadog")
    )
    with pytest.raises(validator.ValidationError) as excinfo:
        intent_authoring.save(project_root, cap)
    # Slug and item id are in the message
    msgs = excinfo.value.errors
    assert any("u-prov" in m and "bogus" in m and "datadog" in m for m in msgs)
    assert any("scanned" in m for m in msgs)
    # File should NOT have been written
    target = intent_authoring.intent_path(project_root, "u-prov")
    assert not target.exists()


def test_unknown_effort_raises(project_root: Path, fake_skills_root: Path) -> None:
    cap = default_capability("eff", "@me")
    # Replace the seed item with one that has a bogus effort
    cap = intent_authoring.upsert_evidence(
        cap, _ev(item_id="first-case", effort="sky-high")
    )
    with pytest.raises(validator.ValidationError) as excinfo:
        intent_authoring.save(project_root, cap)
    assert any("sky-high" in m for m in excinfo.value.errors)


def test_zero_items_raises(project_root: Path, fake_skills_root: Path) -> None:
    cap = default_capability("empty", "@me")
    cap = intent_authoring.remove_item(cap, cap.evidence[0].id)
    assert cap.evidence == [] and cap.constraints == []
    with pytest.raises(validator.ValidationError) as excinfo:
        intent_authoring.save(project_root, cap)
    assert any("at least one way" in m for m in excinfo.value.errors)


def test_happy_path_writes_file(project_root: Path, fake_skills_root: Path) -> None:
    cap = default_capability("happy", "@me")
    out = intent_authoring.save(project_root, cap)
    assert out.exists()
    assert out.name == "happy.md"
    # File is round-trippable
    re_read = intent.parse_intent(out)
    assert re_read.frontmatter.capability == "happy"


def test_dry_run_does_not_write(project_root: Path, fake_skills_root: Path) -> None:
    cap = default_capability("never-saved", "@me")
    out = intent_authoring.save(project_root, cap, dry_run=True)
    assert out.name == "never-saved.md"
    assert not out.exists()


def test_dry_run_still_validates(project_root: Path, fake_skills_root: Path) -> None:
    cap = default_capability("invalid-dry", "@me")
    cap = intent_authoring.upsert_evidence(
        cap, _ev(item_id="first-case", provider="datadog")
    )
    with pytest.raises(validator.ValidationError):
        intent_authoring.save(project_root, cap, dry_run=True)


def test_gate_callable_standalone(project_root: Path, fake_skills_root: Path) -> None:
    """`gate` works without going through `save`."""
    cap = default_capability("standalone", "@me")
    intent_save_gate.gate(cap, project_root)  # does not raise


def test_save_updates_updated_date(
    project_root: Path, fake_skills_root: Path, monkeypatch
) -> None:
    from i2e_core import intent_authoring as ia

    fixed = date(2027, 1, 1)
    monkeypatch.setattr(ia, "today_utc", lambda: fixed)

    cap = default_capability("u-date", "@me")
    # Force created/updated to something else so we can prove `updated` rewrites
    cap.frontmatter.updated = date(2020, 1, 1)
    out = intent_authoring.save(project_root, cap)
    re_read = intent.parse_intent(out)
    assert re_read.frontmatter.updated == fixed
