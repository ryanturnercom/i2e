"""Tests for `i2e_core.develop.diff_against_current`."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from i2e_core import develop, evidence, intent, intent_authoring


def _write_current(
    root: Path,
    *,
    intent_version: int,
    item_ids: list[str],
    failures: dict[str, str] | None = None,
) -> None:
    """Write a minimal `current.yaml` for ``shorten-url``."""
    items: dict[str, evidence.ItemVerdict] = {}
    failures = failures or {}
    for item_id in item_ids:
        if item_id in failures:
            items[item_id] = evidence.ItemVerdict(
                verdict="fail",
                last_observed=datetime(2026, 5, 19, tzinfo=timezone.utc),
                raw={"error": failures[item_id]},
            )
        else:
            items[item_id] = evidence.ItemVerdict(
                verdict="pass",
                last_observed=datetime(2026, 5, 19, tzinfo=timezone.utc),
            )
    cur = evidence.CurrentEvidence(
        capability="shorten-url",
        last_run="2026-05-19-aaaa",
        intent_version=intent_version,
        items=items,
    )
    evidence.write_current(root, cur)


def test_first_run_all_items_new(develop_project: Path):
    diff = develop.diff_against_current(develop_project, "shorten-url")
    assert diff.prior_version is None
    assert diff.current_version == 1
    # 3 evidence items + 2 constraints in the fixture.
    assert len(diff.new_items) == 5
    assert "code-generated" in diff.new_items
    assert "no-open-redirect" in diff.new_items
    assert diff.changed_items == []
    assert diff.removed_items == []
    assert diff.last_failures == []


def test_no_diff_when_versions_match(develop_project: Path):
    item_ids = [
        "code-generated", "redirect-latency-p95", "brand-feel",
        "no-open-redirect", "pii-not-logged",
    ]
    _write_current(develop_project, intent_version=1, item_ids=item_ids)
    diff = develop.diff_against_current(develop_project, "shorten-url")
    assert diff.prior_version == 1
    assert diff.current_version == 1
    assert diff.new_items == []
    assert diff.changed_items == []
    assert diff.removed_items == []


def test_removed_item_appears_in_removed_items(develop_project: Path):
    # Record an item in current.yaml that isn't in the intent.
    item_ids = [
        "code-generated", "redirect-latency-p95", "brand-feel",
        "no-open-redirect", "pii-not-logged",
        "an-old-item-no-longer-in-intent",
    ]
    _write_current(develop_project, intent_version=1, item_ids=item_ids)
    diff = develop.diff_against_current(develop_project, "shorten-url")
    assert diff.removed_items == ["an-old-item-no-longer-in-intent"]
    assert diff.new_items == []


def test_added_item_after_intent_bump(develop_project: Path):
    # current.yaml at v1 with the original 5 items.
    item_ids = [
        "code-generated", "redirect-latency-p95", "brand-feel",
        "no-open-redirect", "pii-not-logged",
    ]
    _write_current(develop_project, intent_version=1, item_ids=item_ids)

    # Now bump the intent to v2 and add a new evidence item.
    intent_path = intent_authoring.intent_path(develop_project, "shorten-url")
    cap = intent.parse_intent(intent_path)
    new_ev = intent.EvidenceItem(
        id="new-case",
        type="case",
        provider="pytest",
        query="tests/test_new.py::test_thing",
        expect="passes",
    )
    cap = intent_authoring.upsert_evidence(cap, new_ev)
    bumped = cap.frontmatter.model_copy(update={"version": 2})
    cap = cap.model_copy(update={"frontmatter": bumped})
    intent.write_intent(cap, intent_path)

    diff = develop.diff_against_current(develop_project, "shorten-url")
    assert diff.prior_version == 1
    assert diff.current_version == 2
    assert "new-case" in diff.new_items
    # All previously known items are reported as "changed" because the intent
    # version moved forward and we can't compare item bodies.
    assert set(diff.changed_items) == set(item_ids)
    assert diff.removed_items == []


def test_last_failures_reported(develop_project: Path):
    item_ids = [
        "code-generated", "redirect-latency-p95", "brand-feel",
        "no-open-redirect", "pii-not-logged",
    ]
    _write_current(
        develop_project,
        intent_version=1,
        item_ids=item_ids,
        failures={"code-generated": "AssertionError: code was 6 chars"},
    )
    diff = develop.diff_against_current(develop_project, "shorten-url")
    assert diff.last_failures == [
        ("code-generated", "AssertionError: code was 6 chars"),
    ]


def test_last_failures_falls_back_to_output(develop_project: Path):
    """When raw.error is absent, raw.output is used."""
    cur = evidence.CurrentEvidence(
        capability="shorten-url",
        last_run="2026-05-19-bbbb",
        intent_version=1,
        items={
            "code-generated": evidence.ItemVerdict(
                verdict="unmet",
                raw={"output": "got 42, wanted <50"},
            ),
        },
    )
    evidence.write_current(develop_project, cur)
    diff = develop.diff_against_current(develop_project, "shorten-url")
    assert diff.last_failures == [("code-generated", "got 42, wanted <50")]


def test_last_failures_empty_when_no_raw(develop_project: Path):
    cur = evidence.CurrentEvidence(
        capability="shorten-url",
        last_run="2026-05-19-cccc",
        intent_version=1,
        items={
            "code-generated": evidence.ItemVerdict(verdict="fail"),
        },
    )
    evidence.write_current(develop_project, cur)
    diff = develop.diff_against_current(develop_project, "shorten-url")
    assert diff.last_failures == [("code-generated", "")]


def test_passing_items_not_in_last_failures(develop_project: Path):
    item_ids = ["code-generated", "redirect-latency-p95"]
    _write_current(
        develop_project, intent_version=1, item_ids=item_ids
    )
    diff = develop.diff_against_current(develop_project, "shorten-url")
    assert diff.last_failures == []
