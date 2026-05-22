"""Tests for `i2e_core.intent`."""

from __future__ import annotations

import os
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


# ---------- parse_intent memoisation ----------

_MINIMAL = (
    "---\n"
    "capability: {cap}\n"
    "created: 2026-01-01\n"
    "updated: 2026-01-01\n"
    "version: {version}\n"
    "status: active\n"
    "---\n"
    "\n"
    "Desc.\n"
    "\n"
    "## Evidence of success\n"
    "\n"
    "- id: a\n"
    "  type: case\n"
    "  provider: pytest\n"
    "  query: q\n"
    "  expect: passes\n"
)


def test_parse_intent_is_memoised(tmp_path: Path):
    """Re-parsing an unchanged file is served from the cache, not re-read."""
    f = tmp_path / "cap-a.md"
    f.write_text(_MINIMAL.format(cap="cap-a", version=1), encoding="utf-8")

    intent._parse_intent_cached.cache_clear()
    intent.parse_intent(f)
    intent.parse_intent(f)
    assert intent._parse_intent_cached.cache_info().hits >= 1


def test_parse_intent_returns_independent_copies(tmp_path: Path):
    """A mutated result must not poison a later parse of the same file."""
    f = tmp_path / "cap-b.md"
    f.write_text(_MINIMAL.format(cap="cap-b", version=1), encoding="utf-8")

    first = intent.parse_intent(f)
    first.frontmatter.version = 999
    first.evidence[0].id = "mutated"
    first.evidence.append(first.evidence[0])

    second = intent.parse_intent(f)
    assert first is not second
    assert second.frontmatter.version == 1
    assert [e.id for e in second.evidence] == ["a"]


def test_parse_intent_reparses_after_edit(tmp_path: Path):
    """An mtime change invalidates the cached parse."""
    f = tmp_path / "cap-c.md"
    f.write_text(_MINIMAL.format(cap="cap-c", version=1), encoding="utf-8")
    assert intent.parse_intent(f).frontmatter.version == 1

    f.write_text(_MINIMAL.format(cap="cap-c", version=2), encoding="utf-8")
    # Force a distinct mtime so the test never flakes on coarse fs resolution.
    st = f.stat()
    os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
    assert intent.parse_intent(f).frontmatter.version == 2
