"""Tests for `i2e_core.develop.needs_develop` and `scoped_capabilities`."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from i2e_core import develop, evidence, intent, intent_authoring
from i2e_core.intent_template import default_capability


def _write_current(root: Path, *, intent_version: int) -> None:
    cur = evidence.CurrentEvidence(
        capability="shorten-url",
        last_run="2026-05-19-aaaa",
        intent_version=intent_version,
        items={
            "code-generated": evidence.ItemVerdict(
                verdict="pass",
                last_observed=datetime(2026, 5, 19, tzinfo=timezone.utc),
            ),
        },
    )
    evidence.write_current(root, cur)


def test_needs_develop_true_when_no_current_yaml(develop_project: Path):
    assert develop.needs_develop(develop_project, "shorten-url") is True


def test_needs_develop_false_when_versions_match(develop_project: Path):
    _write_current(develop_project, intent_version=1)
    assert develop.needs_develop(develop_project, "shorten-url") is False


def test_needs_develop_true_when_intent_newer(develop_project: Path):
    _write_current(develop_project, intent_version=1)
    # Bump intent to v2.
    intent_path = intent_authoring.intent_path(develop_project, "shorten-url")
    cap = intent.parse_intent(intent_path)
    new_fm = cap.frontmatter.model_copy(update={"version": 2})
    intent.write_intent(cap.model_copy(update={"frontmatter": new_fm}), intent_path)
    assert develop.needs_develop(develop_project, "shorten-url") is True


def test_scoped_capabilities_empty_when_no_intents(tmp_path: Path):
    (tmp_path / ".i2e" / "intents").mkdir(parents=True)
    assert develop.scoped_capabilities(tmp_path) == []


def test_scoped_capabilities_no_intents_dir(tmp_path: Path):
    assert develop.scoped_capabilities(tmp_path) == []


def test_scoped_capabilities_returns_active_stale(develop_project: Path):
    # shorten-url is active and has no current.yaml → should be returned.
    caps = develop.scoped_capabilities(develop_project)
    assert [c.frontmatter.capability for c in caps] == ["shorten-url"]


def test_scoped_capabilities_skips_draft(develop_project: Path):
    # Drop a draft intent into the project; it must not be returned.
    draft = default_capability("draftie", "@me")
    intent.write_intent(
        draft,
        intent_authoring.intent_path(develop_project, "draftie"),
    )
    caps = develop.scoped_capabilities(develop_project)
    assert "draftie" not in [c.frontmatter.capability for c in caps]


def test_scoped_capabilities_skips_retired(develop_project: Path):
    retired = default_capability("retiree", "@me")
    retired_fm = retired.frontmatter.model_copy(update={"status": "retired"})
    retired = retired.model_copy(update={"frontmatter": retired_fm})
    intent.write_intent(
        retired,
        intent_authoring.intent_path(develop_project, "retiree"),
    )
    caps = develop.scoped_capabilities(develop_project)
    assert "retiree" not in [c.frontmatter.capability for c in caps]


def test_scoped_capabilities_skips_up_to_date(develop_project: Path):
    _write_current(develop_project, intent_version=1)
    caps = develop.scoped_capabilities(develop_project)
    assert caps == []
