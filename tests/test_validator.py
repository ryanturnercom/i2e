"""Tests for `i2e_core.validator`."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from i2e_core import config, intent, validator


def _make_capability(evidence=None, constraints=None) -> intent.Capability:
    return intent.Capability(
        frontmatter=intent.Frontmatter(
            capability="x",
            created=date(2026, 1, 1),
            updated=date(2026, 1, 1),
            version=1,
            status="active",
            watcher="@me",
        ),
        description="d",
        evidence=evidence or [],
        constraints=constraints or [],
    )


def _evidence(**overrides) -> intent.EvidenceItem:
    data = dict(
        id="a", type="case", provider="pytest", query="q", expect="passes",
        effort="medium",
    )
    data.update(overrides)
    return intent.EvidenceItem.model_validate(data)


def test_empty_capability_rule_3():
    cap = _make_capability()
    with pytest.raises(validator.ValidationError) as excinfo:
        validator.validate_capability(cap)
    assert any("at least one way" in e for e in excinfo.value.errors)


def test_unknown_provider_with_registry(shorten_url_fixture: Path):
    cap = intent.parse_intent(shorten_url_fixture)
    with pytest.raises(validator.ValidationError) as excinfo:
        validator.validate_capability(cap, installed_providers={"pytest"})
    # datadog, human, sentry are unknown -> 3 errors
    msgs = excinfo.value.errors
    assert sum("datadog" in m for m in msgs) == 1
    assert sum("human" in m for m in msgs) == 1
    assert sum("sentry" in m for m in msgs) == 1


def test_provider_check_skipped_when_registry_none(shorten_url_fixture: Path):
    cap = intent.parse_intent(shorten_url_fixture)
    # passes without registry
    validator.validate_capability(cap, installed_providers=None)


def test_aggregates_all_errors():
    cap = _make_capability(
        evidence=[_evidence(id="a", provider="unknown1")],
        constraints=[
            intent.Constraint.model_validate(
                dict(id="b", provider="unknown2", query="q", expect="ok")
            )
        ],
    )
    with pytest.raises(validator.ValidationError) as excinfo:
        validator.validate_capability(cap, installed_providers={"pytest"})
    assert len(excinfo.value.errors) == 2


def test_unknown_effort_with_config():
    cfg = config.default_config()
    cap = _make_capability(evidence=[_evidence(effort="sky-high")])
    with pytest.raises(validator.ValidationError) as excinfo:
        validator.validate_capability_with_config(cap, cfg)
    assert any("sky-high" in e for e in excinfo.value.errors)


def test_unknown_effort_on_constraint():
    cfg = config.default_config()
    cap = _make_capability(
        evidence=[_evidence()],
        constraints=[
            intent.Constraint.model_validate(
                dict(id="c", provider="pytest", query="q", expect="passes",
                     effort="extreme")
            )
        ],
    )
    with pytest.raises(validator.ValidationError) as excinfo:
        validator.validate_capability_with_config(cfg=cfg, cap=cap)
    assert any("extreme" in e for e in excinfo.value.errors)


def test_format_errors_bullets():
    err = validator.ValidationError(["a", "b"])
    formatted = validator.format_errors(err)
    assert "  - a" in formatted
    assert "  - b" in formatted


def test_format_errors_empty():
    err = validator.ValidationError([])
    assert validator.format_errors(err) == "(no errors)"


def test_validate_capability_with_config_happy_path():
    cfg = config.default_config()
    cap = _make_capability(evidence=[_evidence()])
    validator.validate_capability_with_config(
        cap, cfg, installed_providers={"pytest"}
    )


# ── Rule 4: human/subjective providers are Target-only ───────────────────────


def test_human_provider_on_case_rejected():
    cap = _make_capability(
        evidence=[_evidence(id="vibe", type="case", provider="human")]
    )
    with pytest.raises(validator.ValidationError) as excinfo:
        validator.validate_capability(cap)
    assert any(
        "human" in e and "not a target" in e for e in excinfo.value.errors
    )


def test_human_provider_on_constraint_rejected():
    cap = _make_capability(
        evidence=[_evidence()],
        constraints=[
            intent.Constraint.model_validate(
                dict(id="no-bad-vibes", provider="human", query="q", expect="yes")
            )
        ],
    )
    with pytest.raises(validator.ValidationError) as excinfo:
        validator.validate_capability(cap)
    assert any(
        "no-bad-vibes" in e and "not a target" in e
        for e in excinfo.value.errors
    )


def test_survey_provider_on_case_rejected():
    cap = _make_capability(
        evidence=[_evidence(id="nps", type="case", provider="survey")]
    )
    with pytest.raises(validator.ValidationError) as excinfo:
        validator.validate_capability(cap)
    assert any("survey" in e for e in excinfo.value.errors)


def test_human_provider_on_target_allowed():
    cap = _make_capability(
        evidence=[_evidence(id="brand-feel", type="target", provider="human")]
    )
    # A human/subjective provider on a target is the one valid placement.
    validator.validate_capability(cap)
