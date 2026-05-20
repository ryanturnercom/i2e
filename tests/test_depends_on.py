"""Tests for the ``depends_on:`` capability ordering field (spec §2.1, §6.1)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from i2e_core import intent
from i2e_core.orchestrator import DevelopAndEvidence, decide, preflight


_INTENT_TEMPLATE = """---
capability: {name}
created: 2026-05-19
updated: 2026-05-19
version: 1
status: active
watcher: '@me'
{deps_block}---

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


def _deps_block(deps: list[str]) -> str:
    if not deps:
        return ""
    items = "\n".join(f"  - {d}" for d in deps)
    return f"depends_on:\n{items}\n"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    for sub in ("context", "intents", "evidence", "pending", "logs"):
        (tmp_path / ".i2e" / sub).mkdir(parents=True, exist_ok=True)
    return tmp_path


def _write(project: Path, name: str, deps: list[str] | None = None) -> Path:
    p = project / ".i2e" / "intents" / f"{name}.md"
    p.write_text(
        _INTENT_TEMPLATE.format(name=name, deps_block=_deps_block(deps or [])),
        encoding="utf-8",
    )
    return p


def test_depends_on_field_round_trips_through_intent_io(tmp_path: Path) -> None:
    cap = intent.Capability(
        frontmatter=intent.Frontmatter(
            capability="child",
            created=date(2026, 5, 19),
            updated=date(2026, 5, 19),
            version=1,
            status="active",
            watcher="@me",
            depends_on=["parent-a", "parent-b"],
        ),
        description="child cap",
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
    out = tmp_path / "child.md"
    intent.write_intent(cap, out)
    parsed = intent.parse_intent(out)
    assert parsed.frontmatter.depends_on == ["parent-a", "parent-b"]
    # Round-trip equality, including the deps list.
    assert parsed.frontmatter == cap.frontmatter


def test_branch2_picks_parent_before_child(project: Path) -> None:
    # Alphabetical order would pick "alpha-child" first. depends_on must flip it.
    _write(project, "alpha-child", deps=["zulu-parent"])
    _write(project, "zulu-parent")
    action = decide(project)
    assert isinstance(action, DevelopAndEvidence)
    assert action.capability == "zulu-parent"


def test_preflight_rejects_dependency_cycle(project: Path) -> None:
    _write(project, "alpha", deps=["beta"])
    _write(project, "beta", deps=["alpha"])
    result = preflight(project)
    assert result.valid is False
    msgs = [m for errs in result.errors.values() for m in errs]
    assert any("cycle" in m for m in msgs)


def test_preflight_rejects_unknown_dependency(project: Path) -> None:
    _write(project, "alpha", deps=["ghost"])
    result = preflight(project)
    assert result.valid is False
    msgs = [m for errs in result.errors.values() for m in errs]
    assert any("ghost" in m and "unknown" in m for m in msgs)


def test_spec_documents_depends_on_field() -> None:
    spec = (
        Path(__file__).resolve().parent.parent
        / ".documentation"
        / "I2E_simplified.md"
    )
    text = spec.read_text(encoding="utf-8")
    # The field must appear in §2.1 (Intent file schema), §5 (forced-evidence
    # rules — acyclic graph), and §6.1 (decision tree ordering).
    section_21 = text.split("### 2.1")[1].split("### 2.2")[0]
    section_5 = text.split("## 5.")[1].split("## 6.")[0]
    section_61 = text.split("### 6.1")[1].split("### 6.2")[0]
    assert "depends_on" in section_21
    assert "depends_on" in section_5
    assert "depends_on" in section_61


def test_capabilities_without_depends_on_unchanged(project: Path) -> None:
    # No depends_on anywhere — branch 2 must still pick alphabetical first.
    _write(project, "beta")
    _write(project, "alpha")
    action = decide(project)
    assert isinstance(action, DevelopAndEvidence)
    assert action.capability == "alpha"
    # And preflight must remain green.
    assert preflight(project).valid is True
