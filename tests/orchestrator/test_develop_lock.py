"""Develop-lock tests.

``tick()`` claims a worktree lock while developing a capability and
releases it when the capability ships; ``decide()`` skips capabilities
locked by another live instance so concurrent i2e instances swarm
disjoint work.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from i2e_core.io_utils import atomic_write
from i2e_core.orchestrator import (
    DevelopAndEvidence,
    Shippable,
    _ensure_develop_claim,
    decide,
    tick,
)
from i2e_core.swarm import Claim, claim_is_stale, claim_path, read_claim

from .conftest import FakeProvider, always_fail, always_pass


def _basic_evidence() -> list[dict]:
    return [
        {
            "id": "case-a",
            "type": "case",
            "provider": "pytest",
            "query": "tests/test_a.py",
            "expect": "passes",
            "effort": "medium",
        }
    ]


def _plant_claim(
    project: Path, slug: str, *, pid: int, started_at: datetime
) -> Path:
    """Write a worktree claim.json directly, simulating another instance."""
    claim = Claim(
        slug=slug,
        agent_id=f"other-{pid}",
        pid=pid,
        tick_id="2026-05-22-aaaaaa",
        step="develop",
        started_at=started_at,
    )
    target = claim_path(project, slug)
    atomic_write(target, json.dumps(claim.model_dump(mode="json"), indent=2))
    return target


# ---------- claim_is_stale ----------


def test_claim_is_stale_dead_pid():
    claim = Claim(
        slug="x", agent_id="a", pid=999_999, tick_id="t", step="develop",
        started_at=datetime.now(timezone.utc),
    )
    assert claim_is_stale(claim) is True


def test_claim_is_stale_ttl_exceeded():
    old = datetime.now(timezone.utc) - timedelta(minutes=90)
    claim = Claim(
        slug="x", agent_id="a", pid=os.getpid(), tick_id="t", step="develop",
        started_at=old,
    )
    assert claim_is_stale(claim, ttl_minutes=60) is True


def test_claim_is_stale_fresh_and_alive():
    claim = Claim(
        slug="x", agent_id="a", pid=os.getpid(), tick_id="t", step="develop",
        started_at=datetime.now(timezone.utc),
    )
    assert claim_is_stale(claim, ttl_minutes=60) is False


# ---------- _ensure_develop_claim ----------


def test_ensure_claim_acquires_when_absent(project: Path):
    assert _ensure_develop_claim(project, "alpha", "tick-1") is True
    claim = read_claim(project, "alpha")
    assert claim is not None
    assert claim.pid == os.getpid()
    assert claim.step == "develop"


def test_ensure_claim_is_idempotent_for_owner(project: Path):
    _ensure_develop_claim(project, "alpha", "tick-1")
    # Same process re-entering on a later tick keeps its own claim.
    assert _ensure_develop_claim(project, "alpha", "tick-2") is True


def test_ensure_claim_refused_when_held_by_live_other(project: Path):
    _plant_claim(
        project, "alpha", pid=os.getppid(), started_at=datetime.now(timezone.utc)
    )
    assert _ensure_develop_claim(project, "alpha", "tick-1") is False


def test_ensure_claim_takes_over_stale(project: Path):
    _plant_claim(
        project,
        "alpha",
        pid=os.getppid(),
        started_at=datetime.now(timezone.utc) - timedelta(minutes=90),
    )
    assert _ensure_develop_claim(project, "alpha", "tick-1") is True
    claim = read_claim(project, "alpha")
    assert claim is not None and claim.pid == os.getpid()


# ---------- decide() respects locks ----------


def test_decide_skips_capability_locked_by_other(
    project: Path, write_intent, patch_providers
):
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent("alpha", evidence=_basic_evidence(), version=1)
    _plant_claim(
        project, "alpha", pid=os.getppid(), started_at=datetime.now(timezone.utc)
    )
    # alpha is the only capability and it is locked by a live other
    # instance — nothing for this instance to do.
    assert isinstance(decide(project), Shippable)


def test_decide_does_not_skip_own_claim(
    project: Path, write_intent, patch_providers
):
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent("alpha", evidence=_basic_evidence(), version=1)
    _plant_claim(
        project, "alpha", pid=os.getpid(), started_at=datetime.now(timezone.utc)
    )
    act = decide(project)
    assert isinstance(act, DevelopAndEvidence)
    assert act.capability == "alpha"


def test_decide_does_not_skip_stale_claim(
    project: Path, write_intent, patch_providers
):
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent("alpha", evidence=_basic_evidence(), version=1)
    _plant_claim(
        project,
        "alpha",
        pid=os.getppid(),
        started_at=datetime.now(timezone.utc) - timedelta(minutes=90),
    )
    assert isinstance(decide(project), DevelopAndEvidence)


# ---------- tick() lock lifecycle ----------


def test_tick_develop_writes_claim(
    project: Path, write_intent, patch_providers, monkeypatch
):
    """A develop tick on a not-yet-green capability leaves a live claim."""
    patch_providers({"pytest": FakeProvider("pytest", always_fail())})
    write_intent("alpha", evidence=_basic_evidence(), version=1)
    monkeypatch.setattr("i2e_core.orchestrator.render", lambda root: None)

    result = tick(project)
    assert isinstance(result.action, DevelopAndEvidence)

    claim = read_claim(project, "alpha")
    assert claim is not None
    assert claim.pid == os.getpid()
    assert claim.step == "develop"


def test_tick_releases_claim_on_ship(
    project: Path, write_intent, patch_providers, monkeypatch
):
    """When a capability ships, its develop lock is released."""
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent("alpha", evidence=_basic_evidence(), version=1)
    monkeypatch.setattr("i2e_core.orchestrator.render", lambda root: None)

    result = tick(project)
    assert any(
        a.startswith("promoted_to_shipped: alpha") for a in result.actions_log
    )
    assert read_claim(project, "alpha") is None


def test_tick_logs_skip_when_claim_lost(
    project: Path, write_intent, patch_providers, monkeypatch
):
    """A lost race (claim grabbed between decide and tick) is logged."""
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent("alpha", evidence=_basic_evidence(), version=1)
    monkeypatch.setattr("i2e_core.orchestrator.render", lambda root: None)
    monkeypatch.setattr(
        "i2e_core.orchestrator._ensure_develop_claim", lambda *a, **k: False
    )

    result = tick(project)
    assert isinstance(result.action, DevelopAndEvidence)
    assert any(
        a.startswith("skipped_develop: alpha") for a in result.actions_log
    )
