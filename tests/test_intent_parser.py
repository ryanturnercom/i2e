"""Tests for `i2e_core.intent`."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError

from i2e_core import intent


def test_parse_fixture_capability(shorten_url_fixture: Path):
    cap = intent.parse_intent(shorten_url_fixture)
    assert cap.frontmatter.capability == "shorten-url"
    assert cap.frontmatter.created == date(2026, 5, 19)
    assert cap.frontmatter.version == 1
    assert cap.frontmatter.status == "active"
    assert cap.frontmatter.watcher == "@platform-team"
    assert len(cap.evidence) == 3
    assert len(cap.constraints) == 2
    assert cap.evidence[0].id == "code-generated"
    assert cap.evidence[0].type == "case"
    assert cap.evidence[1].window == "5m"
    # multi-line query preserved
    assert "Open the shortener" in cap.evidence[2].query
    assert "Shorten a URL" in cap.description


def test_roundtrip_serialize(shorten_url_fixture: Path, tmp_path: Path):
    cap = intent.parse_intent(shorten_url_fixture)
    out = tmp_path / "out.md"
    intent.write_intent(cap, out)
    cap2 = intent.parse_intent(out)
    assert cap2.frontmatter == cap.frontmatter
    assert cap2.description == cap.description
    assert cap2.evidence == cap.evidence
    assert cap2.constraints == cap.constraints


def test_missing_constraints_section(tmp_path: Path):
    f = tmp_path / "x.md"
    f.write_text(
        "---\n"
        "capability: x\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "version: 1\n"
        "status: active\n"
        "---\n"
        "\n"
        "Desc\n"
        "\n"
        "## Evidence of success\n"
        "\n"
        "- id: a\n"
        "  type: case\n"
        "  provider: pytest\n"
        "  query: tests/test_a.py\n"
        "  expect: passes\n"
        "  effort: medium\n",
        encoding="utf-8",
    )
    cap = intent.parse_intent(f)
    assert cap.constraints == []
    assert len(cap.evidence) == 1


def test_missing_required_field(tmp_path: Path):
    f = tmp_path / "bad.md"
    f.write_text(
        "---\n"
        "capability: x\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "version: 1\n"
        "status: active\n"
        "---\n"
        "\n"
        "## Evidence of success\n"
        "\n"
        "- id: a\n"
        "  type: case\n"
        "  provider: pytest\n"
        # missing query + expect
        "  effort: medium\n",
        encoding="utf-8",
    )
    with pytest.raises(PydanticValidationError):
        intent.parse_intent(f)


def test_kebab_validator_rejects_bad_ids(tmp_path: Path):
    for bad_id in ("myItem", "my_item", "MyItem"):
        f = tmp_path / "bad.md"
        f.write_text(
            "---\n"
            "capability: x\n"
            "created: 2026-01-01\n"
            "updated: 2026-01-01\n"
            "version: 1\n"
            "status: active\n"
            "---\n"
            "\n"
            "## Evidence of success\n"
            "\n"
            f"- id: {bad_id}\n"
            "  type: case\n"
            "  provider: pytest\n"
            "  query: q\n"
            "  expect: passes\n",
            encoding="utf-8",
        )
        with pytest.raises(PydanticValidationError):
            intent.parse_intent(f)


def test_kebab_accepts_lower_kebab():
    item = intent.EvidenceItem(
        id="redirect-latency-p95",
        type="target",
        provider="datadog",
        query="q",
        expect="<50ms",
    )
    assert item.id == "redirect-latency-p95"


def test_description_with_subheadings(tmp_path: Path):
    f = tmp_path / "x.md"
    f.write_text(
        "---\n"
        "capability: x\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "version: 1\n"
        "status: active\n"
        "---\n"
        "\n"
        "# Title\n"
        "\n"
        "## Background\n"
        "\n"
        "Some context.\n"
        "\n"
        "## Evidence of success\n"
        "\n"
        "- id: a\n"
        "  type: case\n"
        "  provider: pytest\n"
        "  query: q\n"
        "  expect: passes\n",
        encoding="utf-8",
    )
    cap = intent.parse_intent(f)
    assert "## Background" in cap.description
    assert len(cap.evidence) == 1
