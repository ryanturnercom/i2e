"""Guards on the i2e-develop SKILL.md — must instruct the skill to read
the source spec when an intent's frontmatter points at one.

This capability is prompt-only (no Python helper), so the regression
guards live in the SKILL.md text. Bundled copies under ``dist/`` must
stay in sync with the source under ``.claude/skills/``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SOURCE_SKILL = _REPO_ROOT / ".claude" / "skills" / "i2e-develop" / "SKILL.md"
_BUNDLED_SKILLS = [
    _REPO_ROOT / "dist" / "agentskills" / "i2e-develop" / "SKILL.md",
    _REPO_ROOT
    / "dist"
    / "claude-plugin"
    / "plugins"
    / "i2e"
    / "skills"
    / "i2e-develop"
    / "SKILL.md",
]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_skill_md_declares_spec_read() -> None:
    body = _read(_SOURCE_SKILL)
    # The READ surface must list the spec path.
    assert ".i2e/specs/<slug>.md" in body, (
        "i2e-develop SKILL.md must declare .i2e/specs/<slug>.md in its READ surface "
        "so parallel sub-agents can see the narrative rationale that produced the intent."
    )


def test_skill_md_workflow_step_for_spec() -> None:
    body = _read(_SOURCE_SKILL).lower()
    # Workflow must instruct the skill to actually open the file.
    assert "frontmatter" in body and "spec:" in body, (
        "SKILL.md must reference reading the spec when the intent's frontmatter "
        "has spec:"
    )
    assert "spec_section" in body, (
        "SKILL.md should mention spec_section so the skill knows to slice when set."
    )


@pytest.mark.parametrize("bundled", _BUNDLED_SKILLS, ids=lambda p: p.parent.parent.name)
def test_bundled_skill_md_matches_source(bundled: Path) -> None:
    if not bundled.exists():
        pytest.skip(f"bundle not built yet: {bundled}")
    assert _read(bundled) == _read(_SOURCE_SKILL), (
        f"{bundled} drifted from the source SKILL.md — re-run ./tasks.ps1 bundle"
    )


def test_write_surface_unchanged() -> None:
    body = _read(_SOURCE_SKILL)
    # The skill must still write only src/ + tests/. Surface this as an explicit
    # assertion so an accidental change to the WRITE clause fails loudly.
    assert "WRITE: `src/**`, `tests/**` only" in body
    assert "NEVER WRITE: anything under `.i2e/`" in body
