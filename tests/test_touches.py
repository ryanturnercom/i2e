"""Tests for the ``touches:`` declared-file-scope field (spec §2.1, §4.1)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from i2e_core import intent
from i2e_core.touches import paths_outside_touches, paths_overlap


_INTENT_TEMPLATE = """---
capability: {name}
created: 2026-05-19
updated: 2026-05-19
version: 1
status: active
watcher: '@me'
{touches_block}---

# {name}

## Evidence of success

- id: case-a
  type: case
  provider: pytest
  query: tests/a.py
  expect: passes
  effort: medium

## Constraints

"""


def _touches_block(globs: list[str] | None) -> str:
    if globs is None:
        return ""
    items = "\n".join(f"  - {g!r}" for g in globs)
    return f"touches:\n{items}\n"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    for sub in ("context", "intents", "evidence", "pending", "logs"):
        (tmp_path / ".i2e" / sub).mkdir(parents=True, exist_ok=True)
    return tmp_path


def _write(
    project: Path, name: str, touches: list[str] | None = None
) -> Path:
    p = project / ".i2e" / "intents" / f"{name}.md"
    p.write_text(
        _INTENT_TEMPLATE.format(name=name, touches_block=_touches_block(touches)),
        encoding="utf-8",
    )
    return p


def test_touches_field_round_trips_through_intent_io(tmp_path: Path) -> None:
    cap = intent.Capability(
        frontmatter=intent.Frontmatter(
            capability="scoped",
            created=date(2026, 5, 19),
            updated=date(2026, 5, 19),
            version=1,
            status="active",
            watcher="@me",
            touches=["src/scoped/**", "tests/test_scoped.py"],
        ),
        description="scoped cap",
        evidence=[
            intent.EvidenceItem(
                id="ev",
                type="case",
                provider="pytest",
                query="tests/x.py",
                expect="passes",
                effort="medium",
            )
        ],
    )
    out = tmp_path / "scoped.md"
    intent.write_intent(cap, out)
    parsed = intent.parse_intent(out)
    assert parsed.frontmatter.touches == [
        "src/scoped/**",
        "tests/test_scoped.py",
    ]
    assert parsed.frontmatter == cap.frontmatter


def test_paths_overlap_detects_glob_intersection() -> None:
    # Non-overlapping siblings under src/.
    assert paths_overlap(["src/foo/**"], ["src/bar/**"]) is False
    # Same prefix overlaps.
    assert paths_overlap(["src/foo/**"], ["src/foo/**"]) is True
    # Parent/child overlaps.
    assert paths_overlap(["src/foo/**"], ["src/foo/bar/**"]) is True
    # Segment-aware: src/foo must NOT match src/foobar.
    assert paths_overlap(["src/foo/**"], ["src/foobar/**"]) is False
    # Global ** overlaps with anything.
    assert paths_overlap(["**"], ["src/anywhere/**"]) is True
    assert paths_overlap(["src/x/**"], ["**"]) is True
    # Cross-directory non-overlap (src vs tests).
    assert (
        paths_overlap(["src/foo/**"], ["tests/test_bar.py"]) is False
    )
    # Multi-glob list — overlap if any pair matches.
    assert (
        paths_overlap(
            ["src/foo/**", "tests/test_foo.py"],
            ["docs/**", "tests/test_foo.py"],
        )
        is True
    )


def test_develop_post_check_rejects_writes_outside_touches() -> None:
    touches = ["src/foo/**", "tests/test_foo.py"]
    in_scope = [
        Path("src/foo/core.py"),
        Path("src/foo/sub/util.py"),
        Path("tests/test_foo.py"),
    ]
    assert paths_outside_touches(touches, in_scope) == []

    written = [
        Path("src/foo/core.py"),       # ok
        Path("src/bar/leaked.py"),     # NOT ok — outside touches
        Path("tests/test_foo.py"),     # ok
        Path("docs/README.md"),        # NOT ok
    ]
    violations = paths_outside_touches(touches, written)
    # Forward-slash normalized, ordered as encountered.
    assert violations == ["src/bar/leaked.py", "docs/README.md"]


def test_capability_without_touches_defaults_to_global_scope(
    project: Path,
) -> None:
    p = _write(project, "no-touches", touches=None)
    cap = intent.parse_intent(p)
    # Missing touches → defaults to the wildcard, matching every path.
    assert cap.frontmatter.touches == ["**"]
    # And develop is therefore unconstrained for legacy capabilities.
    assert paths_outside_touches(cap.frontmatter.touches, [Path("anywhere/file.py")]) == []


def test_spec_documents_touches_field() -> None:
    spec = (
        Path(__file__).resolve().parent.parent
        / ".documentation"
        / "I2E_simplified.md"
    )
    text = spec.read_text(encoding="utf-8")
    section_21 = text.split("### 2.1")[1].split("### 2.2")[0]
    section_41 = text.split("### 4.1")[1].split("### 4.2")[0]
    section_11 = text.split("## 11.")[1].split("## 12.")[0]
    assert "touches" in section_21
    assert "touches" in section_41
    # §11 must gain the new principle.
    assert (
        "Declared file scope" in section_11
        or "touches" in section_11
    )


def test_existing_capabilities_unaffected(
    project: Path, shorten_url_fixture: Path
) -> None:
    """A capability written before touches: existed must:
       - Parse without error.
       - Default to touches=['**'].
       - Round-trip without gaining a touches: line in its serialized form.
    """
    # Use the canonical fixture (no touches: field) as the legacy example.
    cap = intent.parse_intent(shorten_url_fixture)
    assert cap.frontmatter.touches == ["**"]

    out = project / "round-trip.md"
    intent.write_intent(cap, out)
    text = out.read_text(encoding="utf-8")
    # The default scope must not be written back to disk — fixture stays clean.
    assert "touches:" not in text.split("---", 2)[1]
