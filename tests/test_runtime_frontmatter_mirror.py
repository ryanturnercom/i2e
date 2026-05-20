"""Tests for the runtime-frontmatter-mirror slice (swarm-tick §2)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from i2e_core import intent
from i2e_core.swarm import (
    acquire_claim,
    clear_runtime,
    mirror_runtime,
    read_runtime,
    release_claim,
)


_INTENT = """---
capability: alpha
created: 2026-05-19
updated: 2026-05-19
version: 1
status: active
watcher: '@me'
depends_on:
- root-of-things
touches:
- src/i2e_core/foo.py
- tests/test_foo.py
---

# alpha

Test capability.

## Evidence of success

- id: case-a
  type: case
  provider: pytest
  query: tests/test_alpha.py
  expect: passes
  effort: medium

## Constraints

"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    for sub in ("context", "intents", "evidence", "pending", "logs"):
        (tmp_path / ".i2e" / sub).mkdir(parents=True, exist_ok=True)
    # Need at least one parent for depends_on to resolve.
    (tmp_path / ".i2e" / "intents" / "root-of-things.md").write_text(
        textwrap.dedent(
            """---
capability: root-of-things
created: 2026-05-19
updated: 2026-05-19
version: 1
status: active
watcher: '@me'
---

## Evidence of success

- id: c
  type: case
  provider: pytest
  query: t
  expect: passes
  effort: medium

## Constraints

"""
        ),
        encoding="utf-8",
    )
    (tmp_path / ".i2e" / "intents" / "alpha.md").write_text(
        textwrap.dedent(_INTENT), encoding="utf-8"
    )
    return tmp_path


def test_implemented(project: Path) -> None:
    """Mirror writes runtime; clear removes it; other fields untouched."""
    # Snapshot fields we expect to be preserved verbatim.
    before = intent.parse_intent(
        project / ".i2e" / "intents" / "alpha.md"
    )
    assert before.frontmatter.runtime is None

    claim = acquire_claim(
        project,
        "alpha",
        tick_id="2026-05-20-aaa000",
        step="develop",
        session_id="session-x",
        progress="initialising",
    )

    written_path = mirror_runtime(project, claim)
    assert written_path is not None and written_path.exists()

    after = intent.parse_intent(written_path)
    rt = after.frontmatter.runtime
    assert rt is not None
    assert rt["agent_id"] == claim.agent_id
    assert rt["session_id"] == "session-x"
    assert rt["tick_id"] == "2026-05-20-aaa000"
    assert rt["step"] == "develop"
    assert "2026" in rt["started_at"]
    assert rt["worktree"].endswith("/alpha") or rt["worktree"].endswith(
        "\\alpha"
    )

    # The mirror preserves every other field.
    assert after.frontmatter.capability == before.frontmatter.capability
    assert after.frontmatter.status == before.frontmatter.status
    assert after.frontmatter.depends_on == before.frontmatter.depends_on
    assert after.frontmatter.touches == before.frontmatter.touches
    assert after.frontmatter.version == before.frontmatter.version
    assert after.description.strip() == before.description.strip()
    assert [e.id for e in after.evidence] == [e.id for e in before.evidence]

    # read_runtime returns the same payload.
    assert read_runtime(project, "alpha") == rt

    # Clear strips the block; other fields still untouched.
    cleared_path = clear_runtime(project, "alpha")
    assert cleared_path == written_path
    final = intent.parse_intent(written_path)
    assert final.frontmatter.runtime is None
    assert final.frontmatter.status == before.frontmatter.status
    assert final.frontmatter.depends_on == before.frontmatter.depends_on
    assert final.frontmatter.touches == before.frontmatter.touches
    # And the serialized file contains no `runtime:` key on disk.
    text = written_path.read_text(encoding="utf-8")
    fm_block = text.split("---", 2)[1]
    assert "runtime:" not in fm_block

    release_claim(project, "alpha")


def test_clear_runtime_is_idempotent(project: Path) -> None:
    # No runtime block yet — clearing must not crash and must be a no-op.
    assert clear_runtime(project, "alpha") is None
    # Still no runtime block; subsequent read returns None.
    assert read_runtime(project, "alpha") is None


def test_mirror_runtime_skips_missing_intent(project: Path) -> None:
    claim = acquire_claim(
        project,
        "no-such-intent",
        tick_id="2026-05-20-zzz000",
        step="evidence",
    )
    assert mirror_runtime(project, claim) is None
    release_claim(project, "no-such-intent")


def test_deleting_runtime_block_does_not_release_actual_lock(
    project: Path,
) -> None:
    """Frontmatter is a mirror, not the source of truth.

    The lock is the worktree directory. Manually clearing the runtime
    frontmatter must NOT make the worktree re-claimable while a live
    PID still owns it.
    """
    claim = acquire_claim(
        project,
        "alpha",
        tick_id="2026-05-20-bbb000",
        step="develop",
    )
    mirror_runtime(project, claim)

    # Surgically remove the runtime block by hand.
    cleared_path = clear_runtime(project, "alpha")
    assert cleared_path is not None
    # The worktree directory still exists — lock is held.
    from i2e_core.swarm import worktree_dir

    assert worktree_dir(project, "alpha").exists()
    # A second acquire MUST still raise.
    with pytest.raises(FileExistsError):
        acquire_claim(
            project,
            "alpha",
            tick_id="2026-05-20-ccc000",
            step="develop",
        )
    release_claim(project, "alpha")
