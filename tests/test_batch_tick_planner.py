"""Tests for the batch-tick-planner slice (swarm-tick §3)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from i2e_core.swarm import plan_batch


_INTENT = """---
capability: {name}
created: 2026-05-19
updated: 2026-05-19
version: 1
status: active
watcher: '@me'
{deps}{touches}---

# {name}

## Evidence of success

- id: case-a
  type: case
  provider: pytest
  query: q
  expect: passes
  effort: medium

## Constraints

"""


def _deps(items: list[str] | None) -> str:
    if not items:
        return ""
    rendered = "\n".join(f"  - {i}" for i in items)
    return f"depends_on:\n{rendered}\n"


def _touches(items: list[str]) -> str:
    rendered = "\n".join(f"  - {i!r}" for i in items)
    return f"touches:\n{rendered}\n"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    for sub in ("context", "intents", "evidence", "pending", "logs"):
        (tmp_path / ".i2e" / sub).mkdir(parents=True, exist_ok=True)
    return tmp_path


def _write(
    project: Path,
    name: str,
    *,
    touches: list[str],
    depends_on: list[str] | None = None,
) -> Path:
    body = _INTENT.format(
        name=name,
        deps=_deps(depends_on),
        touches=_touches(touches),
    )
    p = project / ".i2e" / "intents" / f"{name}.md"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def test_implemented(project: Path) -> None:
    """Cover the four interesting cases of the planner in one go.

    (a) Three non-overlapping touches => batch of three, alphabetical.
    (b) Two overlapping touches       => only the alphabetical-first wins.
    (c) Child held back by depends_on => only the parent gets dispatched.
    (d) Single eligible capability    => single-element batch (no overhead).
    """

    # --- (a) three independent files ------------------------------------
    _write(project, "alpha", touches=["src/alpha/**", "tests/test_alpha.py"])
    _write(project, "beta", touches=["src/beta/**", "tests/test_beta.py"])
    _write(project, "gamma", touches=["src/gamma/**", "tests/test_gamma.py"])
    batch = plan_batch(project)
    assert batch == ["alpha", "beta", "gamma"]

    # --- (b) overlap collapses the batch --------------------------------
    # Add "alpha-2" that touches the same dir as "alpha"; planner should
    # serialize it for a later tick rather than emit both.
    _write(
        project,
        "alpha-2",
        touches=["src/alpha/**", "tests/test_alpha_2.py"],
    )
    batch = plan_batch(project)
    # alpha (alphabetical first on src/alpha/**) keeps the slot; alpha-2 waits.
    assert "alpha" in batch
    assert "alpha-2" not in batch
    # The two non-overlapping ones still ride along.
    assert "beta" in batch
    assert "gamma" in batch


def test_depends_on_holds_child_back(project: Path) -> None:
    _write(project, "parent", touches=["src/parent/**", "tests/test_parent.py"])
    _write(
        project,
        "child",
        touches=["src/child/**", "tests/test_child.py"],
        depends_on=["parent"],
    )
    batch = plan_batch(project)
    assert batch == ["parent"]


def test_single_eligible_capability_is_single_element_batch(
    project: Path,
) -> None:
    _write(project, "solo", touches=["src/solo/**", "tests/test_solo.py"])
    assert plan_batch(project) == ["solo"]


def test_shippable_project_returns_empty_batch(project: Path) -> None:
    # No intents at all -> nothing scoped -> empty batch.
    assert plan_batch(project) == []
