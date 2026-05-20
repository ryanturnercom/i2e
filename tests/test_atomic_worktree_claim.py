"""Tests for the atomic-worktree-claim slice (swarm-tick §1)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from i2e_core.swarm import (
    Claim,
    acquire_claim,
    claim_path,
    is_pid_alive,
    read_claim,
    release_claim,
    sweep_stale,
    worktree_dir,
)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / ".i2e").mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_implemented(project: Path) -> None:
    """End-to-end smoke: acquire, observe claim.json fields, release."""
    claim = acquire_claim(
        project,
        "alpha",
        tick_id="2026-05-20-aaa000",
        step="develop",
        session_id="session-x",
    )
    assert isinstance(claim, Claim)
    assert claim.slug == "alpha"
    assert claim.pid == os.getpid()
    assert claim.tick_id == "2026-05-20-aaa000"
    assert claim.step == "develop"
    assert claim.session_id == "session-x"
    assert claim.agent_id  # non-empty UUID
    assert claim.started_at is not None

    # The on-disk file matches what we got back.
    written = json.loads(
        claim_path(project, "alpha").read_text(encoding="utf-8")
    )
    assert written["slug"] == "alpha"
    assert written["pid"] == os.getpid()

    # A second acquire on the same slug must fail while the claim is live.
    with pytest.raises(FileExistsError):
        acquire_claim(
            project,
            "alpha",
            tick_id="2026-05-20-bbb000",
            step="develop",
        )

    # Release frees it; the worktree directory is gone afterwards.
    assert release_claim(project, "alpha") is True
    assert not worktree_dir(project, "alpha").exists()
    # Idempotent on a fresh project.
    assert release_claim(project, "alpha") is False


def test_read_claim_returns_none_when_missing(project: Path) -> None:
    assert read_claim(project, "nothing") is None


def test_sweep_stale_reclaims_dead_pid(project: Path) -> None:
    """A claim whose PID is dead must be sweepable; a live one must not."""
    # Forge a stale claim by hand (no os.kill needed — we just record a
    # PID that cannot exist on any sane system).
    target = worktree_dir(project, "ghost")
    target.mkdir(parents=True)
    fake = {
        "slug": "ghost",
        "agent_id": "00000000-0000-0000-0000-000000000000",
        "session_id": None,
        "pid": 0,  # treated as dead by is_pid_alive
        "tick_id": "2026-05-20-zzz999",
        "step": "develop",
        "started_at": "2026-05-20T00:00:00+00:00",
        "progress": "",
    }
    claim_path(project, "ghost").write_text(
        json.dumps(fake), encoding="utf-8"
    )

    assert sweep_stale(project, "ghost") is True
    assert not target.exists()

    # A fresh, live claim on the same slug must succeed.
    fresh = acquire_claim(
        project,
        "ghost",
        tick_id="2026-05-20-ccc000",
        step="evidence",
    )
    assert fresh.pid == os.getpid()

    # And the live claim is NOT sweepable.
    assert sweep_stale(project, "ghost") is False
    release_claim(project, "ghost")


def test_is_pid_alive_treats_zero_and_negative_as_dead() -> None:
    assert is_pid_alive(0) is False
    assert is_pid_alive(-1) is False


def test_is_pid_alive_recognises_current_process() -> None:
    assert is_pid_alive(os.getpid()) is True


def test_acquire_reclaims_empty_worktree_directory(project: Path) -> None:
    """A leftover worktree dir with no claim.json must not block a fresh claim.

    This is the recovery scenario: a previous run crashed after mkdir
    but before atomic_write completed.
    """
    target = worktree_dir(project, "orphan")
    target.mkdir(parents=True)
    # No claim.json inside.
    claim = acquire_claim(
        project,
        "orphan",
        tick_id="2026-05-20-ddd000",
        step="develop",
    )
    assert claim.slug == "orphan"
    assert claim_path(project, "orphan").exists()
    release_claim(project, "orphan")
