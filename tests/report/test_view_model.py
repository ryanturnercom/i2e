"""View-model builder tests."""

from __future__ import annotations

from pathlib import Path

from i2e_core.report.view_model import build_view_model


def _basic_evidence() -> list[dict]:
    return [
        {
            "id": "case-a",
            "type": "case",
            "provider": "pytest",
            "query": "q",
            "expect": "passes",
            "effort": "medium",
        },
        {
            "id": "target-b",
            "type": "target",
            "provider": "datadog",
            "query": "m",
            "expect": "<50ms",
            "window": "5m",
            "effort": "low",
        },
    ]


def test_empty_project_returns_empty_model(project: Path) -> None:
    vm = build_view_model(project)
    assert vm.capabilities == []
    assert vm.pending == []
    assert vm.ticks == []
    # Shippable is False when there are no capabilities (nothing to ship).
    assert vm.shippable is False


def test_one_capability_three_items(
    project: Path, write_intent, write_current_for
) -> None:
    write_intent(
        "alpha",
        evidence=_basic_evidence(),
        constraints=[
            {
                "id": "no-leak",
                "provider": "pytest",
                "query": "tests/x.py",
                "expect": "passes",
                "effort": "high",
            }
        ],
        version=1,
    )
    write_current_for(
        "alpha",
        {
            "case-a": {"verdict": "pass", "attempts_used": 1},
            "target-b": {"verdict": "trending", "attempts_used": 2},
            "no-leak": {"verdict": "fail", "attempts_used": 1},
        },
        intent_version=1,
    )
    vm = build_view_model(project)
    assert len(vm.capabilities) == 1
    cap = vm.capabilities[0]
    assert cap.slug == "alpha"
    assert [i.id for i in cap.items] == ["case-a", "no-leak", "target-b"]
    # max_attempts comes from config:
    # case medium=6, constraint(=case map) high=10, target low=1
    max_by_id = {i.id: i.max_attempts for i in cap.items}
    assert max_by_id == {"case-a": 6, "no-leak": 10, "target-b": 1}
    assert vm.shippable is False  # mixed verdicts


def test_shippable_only_when_all_green(
    project: Path, write_intent, write_current_for
) -> None:
    write_intent("alpha", evidence=_basic_evidence(), version=1)
    write_current_for(
        "alpha",
        {
            "case-a": {"verdict": "pass", "attempts_used": 0},
            "target-b": {"verdict": "met", "attempts_used": 0},
        },
        intent_version=1,
    )
    vm = build_view_model(project)
    assert vm.shippable is True

    # One failing item flips it back.
    write_current_for(
        "alpha",
        {
            "case-a": {"verdict": "pass", "attempts_used": 0},
            "target-b": {"verdict": "fail", "attempts_used": 1},
        },
        intent_version=1,
    )
    vm = build_view_model(project)
    assert vm.shippable is False


def test_skips_non_active_intents(
    project: Path, write_intent, write_current_for
) -> None:
    write_intent("draft-cap", evidence=_basic_evidence(), version=1, status="draft")
    write_intent("retired-cap", evidence=_basic_evidence(), version=1, status="retired")
    vm = build_view_model(project)
    assert vm.capabilities == []


def test_drafts_listed_separately(
    project: Path, write_intent, write_current_for
) -> None:
    write_intent("alpha", evidence=_basic_evidence(), version=1, status="active")
    write_intent("zeta-draft", evidence=_basic_evidence(), version=1, status="draft")
    write_intent("beta-draft", evidence=_basic_evidence(), version=1, status="draft")
    vm = build_view_model(project)
    assert [c.slug for c in vm.capabilities] == ["alpha"]
    assert [c.slug for c in vm.drafts] == ["beta-draft", "zeta-draft"]
    # Drafts with no current.yaml render their items as "no data".
    draft = vm.drafts[0]
    assert all(i.verdict == "none" for i in draft.items)


def test_active_capabilities_excludes_drafts(
    project: Path, write_intent, write_current_for
) -> None:
    write_intent("draft-cap", evidence=_basic_evidence(), version=1, status="draft")
    write_intent("active-cap", evidence=_basic_evidence(), version=1, status="active")
    vm = build_view_model(project)
    active_slugs = [c.slug for c in vm.capabilities]
    assert "draft-cap" not in active_slugs
    assert active_slugs == ["active-cap"]


def test_shippable_ignores_drafts(
    project: Path, write_intent, write_current_for
) -> None:
    # Active capability is fully green.
    write_intent("alpha", evidence=_basic_evidence(), version=1, status="active")
    write_current_for(
        "alpha",
        {
            "case-a": {"verdict": "pass", "attempts_used": 0},
            "target-b": {"verdict": "met", "attempts_used": 0},
        },
        intent_version=1,
    )
    # Draft has no evidence — would normally make a capability non-shippable.
    write_intent("draft-cap", evidence=_basic_evidence(), version=1, status="draft")
    vm = build_view_model(project)
    assert vm.shippable is True


def test_retired_capabilities_hidden(
    project: Path, write_intent, write_current_for
) -> None:
    write_intent("retired-cap", evidence=_basic_evidence(), version=1, status="retired")
    write_intent("active-cap", evidence=_basic_evidence(), version=1, status="active")
    write_intent("draft-cap", evidence=_basic_evidence(), version=1, status="draft")
    vm = build_view_model(project)
    assert [c.slug for c in vm.capabilities] == ["active-cap"]
    assert [c.slug for c in vm.drafts] == ["draft-cap"]
    # Retired must not appear in either bucket.
    all_slugs = [c.slug for c in vm.capabilities] + [c.slug for c in vm.drafts]
    assert "retired-cap" not in all_slugs


def test_capabilities_sorted_by_slug(
    project: Path, write_intent, write_current_for
) -> None:
    write_intent("zeta", evidence=_basic_evidence(), version=1)
    write_intent("alpha", evidence=_basic_evidence(), version=1)
    write_intent("mu", evidence=_basic_evidence(), version=1)
    vm = build_view_model(project)
    assert [c.slug for c in vm.capabilities] == ["alpha", "mu", "zeta"]
