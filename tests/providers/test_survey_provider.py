"""Tests for ``i2e-provider-survey`` and the numeric resolution extension."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from i2e_core.intent import EvidenceItem
from i2e_core.paths import pending_dir
from i2e_core.pending import (
    PendingFile,
    read_pending,
    resolve_to_verdict,
)
from i2e_core.provider import AsyncResult, ProviderContext
from i2e_core.provider.discovery import installed_provider_names, load_provider


def _item(
    expect: str = ">=8",
    query_obj: dict | None = None,
    item_id: str = "nps-q1",
) -> EvidenceItem:
    if query_obj is None:
        query_obj = {
            "prompt": "How likely are you to recommend?",
            "scale": "nps",
            "followup": "What's the main reason for your score?",
        }
    return EvidenceItem(
        id=item_id,
        type="target",
        provider="survey",
        query=json.dumps(query_obj),
        expect=expect,
    )


# ---------- discovery ----------


def test_discovery_finds_survey(fake_skills_root: Path) -> None:
    names = installed_provider_names(extra_paths=[fake_skills_root])
    assert "survey" in names


def test_load_survey_returns_named_provider(fake_skills_root: Path) -> None:
    provider = load_provider("survey", extra_paths=[fake_skills_root])
    assert provider.name == "survey"


# ---------- write pending ----------


def test_first_call_writes_pending_with_nps_options(
    fake_skills_root: Path, provider_ctx: ProviderContext
) -> None:
    provider = load_provider("survey", extra_paths=[fake_skills_root])
    result = provider.invoke(_item(item_id="nps-1"), provider_ctx)
    assert isinstance(result, AsyncResult)
    assert result.verdict == "awaiting_human"
    written = pending_dir(provider_ctx.root) / result.pending
    assert written.exists()
    pf = read_pending(written)
    assert pf.kind == "human_evaluation"
    assert pf.verdict_options == [str(n) for n in range(0, 11)]
    assert pf.expect == ">=8"
    assert "Net Promoter" in pf.ask
    assert "Follow-up" in pf.ask


def test_likert_scale_options(
    fake_skills_root: Path, provider_ctx: ProviderContext
) -> None:
    provider = load_provider("survey", extra_paths=[fake_skills_root])
    item = _item(
        expect=">=4",
        item_id="likert-1",
        query_obj={"prompt": "Was this easy?", "scale": "likert"},
    )
    result = provider.invoke(item, provider_ctx)
    written = pending_dir(provider_ctx.root) / result.pending
    pf = read_pending(written)
    assert pf.verdict_options == [str(n) for n in range(1, 6)]
    assert "Likert" in pf.ask


def test_unknown_scale_raises(
    fake_skills_root: Path, provider_ctx: ProviderContext
) -> None:
    provider = load_provider("survey", extra_paths=[fake_skills_root])
    item = _item(
        item_id="bad-scale",
        query_obj={"prompt": "x", "scale": "wat"},
    )
    with pytest.raises(ValueError, match="unknown scale"):
        provider.invoke(item, provider_ctx)


def test_invalid_query_raises(
    fake_skills_root: Path, provider_ctx: ProviderContext
) -> None:
    provider = load_provider("survey", extra_paths=[fake_skills_root])
    item = EvidenceItem(
        id="bad-json",
        type="target",
        provider="survey",
        query="not json",
        expect=">=8",
    )
    with pytest.raises(ValueError, match="JSON"):
        provider.invoke(item, provider_ctx)


# ---------- numeric resolution → resolve_to_verdict ----------


def _resolved(
    resolution: str,
    expect: str = ">=8",
    item_id: str = "nps-q1",
) -> PendingFile:
    return PendingFile(
        status="resolved",
        kind="human_evaluation",
        capability="demo",
        item_id=item_id,
        asked_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
        ask="Rate 0-10",
        expect=expect,
        verdict_options=[str(n) for n in range(0, 11)],
        resolution=resolution,
    )


def test_numeric_resolution_met() -> None:
    pf = _resolved("9", expect=">=8")
    v = resolve_to_verdict(pf)
    assert v.verdict == "met"
    assert v.value == "9"


def test_numeric_resolution_unmet() -> None:
    pf = _resolved("5", expect=">=8")
    v = resolve_to_verdict(pf)
    assert v.verdict == "unmet"
    assert v.value == "5"


def test_numeric_resolution_boundary_met() -> None:
    pf = _resolved("8", expect=">=8")
    v = resolve_to_verdict(pf)
    assert v.verdict == "met"


def test_decimal_resolution() -> None:
    pf = _resolved("4.5", expect=">=4")
    v = resolve_to_verdict(pf)
    assert v.verdict == "met"
    assert v.value == "4.5"


def test_numeric_without_comparison_expect_falls_through() -> None:
    """If ``expect`` isn't a comparison, the numeric branch falls through to
    the legacy yes/no/partial branch — and raises because the resolution is
    not recognised there.
    """
    pf = _resolved("8", expect="yes")
    with pytest.raises(ValueError, match="Unrecognised"):
        resolve_to_verdict(pf)


def test_human_yes_resolves_to_met() -> None:
    """The human yes/no/partial branch coexists with the numeric survey branch."""
    pf = PendingFile(
        status="resolved",
        kind="human_evaluation",
        capability="demo",
        item_id="subj",
        asked_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
        ask="?",
        resolution="yes",
    )
    v = resolve_to_verdict(pf)
    assert v.verdict == "met"


def test_human_no_resolves_to_unmet() -> None:
    pf = PendingFile(
        status="resolved",
        kind="human_evaluation",
        capability="demo",
        item_id="subj",
        asked_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
        ask="?",
        resolution="no",
    )
    v = resolve_to_verdict(pf)
    assert v.verdict == "unmet"
