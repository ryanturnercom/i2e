"""Performance + cache tests for the fast-tick-noop capability.

Covers:
- :func:`i2e_core.orchestrator.decide` short-circuits when nothing is active.
- A no-op orchestrator tick completes well under 100ms wall-clock.
- :func:`i2e_core.orchestrator.preflight` caches its result and invalidates
  the cache when any intent file's mtime changes.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from i2e_core.orchestrator import (
    Shippable,
    decide,
    preflight,
    tick,
)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    for sub in ("context", "intents", "evidence", "pending", "logs"):
        (tmp_path / ".i2e" / sub).mkdir(parents=True, exist_ok=True)
    return tmp_path


_VALID_ACTIVE = """---
capability: {name}
created: 2026-05-19
updated: 2026-05-19
version: {version}
status: active
watcher: '@me'
---

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

_VALID_DRAFT = """---
capability: {name}
created: 2026-05-19
updated: 2026-05-19
version: 1
status: draft
watcher: '@me'
---

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

_NO_ITEMS_ACTIVE = """---
capability: {name}
created: 2026-05-19
updated: 2026-05-19
version: 1
status: active
watcher: '@me'
---

# {name}

## Evidence of success

## Constraints

"""


def _write(project: Path, name: str, body: str) -> Path:
    p = project / ".i2e" / "intents" / f"{name}.md"
    p.write_text(body, encoding="utf-8")
    return p


def _bump_mtime(p: Path) -> None:
    """Force mtime_ns to advance regardless of filesystem resolution."""
    st = p.stat()
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))


def test_noop_tick_completes_under_100ms(project: Path) -> None:
    # Warm import paths once; the spec target is steady-state, not cold-start.
    tick(project)
    start = time.perf_counter()
    result = tick(project)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert isinstance(result.action, Shippable)
    assert result.actions_log == []
    assert elapsed_ms < 100, f"noop tick took {elapsed_ms:.1f}ms (target <100ms)"


def test_decide_short_circuits_when_only_drafts(project: Path) -> None:
    _write(project, "wip-a", _VALID_DRAFT.format(name="wip-a"))
    _write(project, "wip-b", _VALID_DRAFT.format(name="wip-b"))
    action = decide(project)
    assert isinstance(action, Shippable)


def test_preflight_cache_invalidates_on_intent_mtime_change(project: Path) -> None:
    p = _write(project, "alpha", _VALID_ACTIVE.format(name="alpha", version=1))
    cache = project / ".i2e" / ".preflight_cache.json"

    assert not cache.exists()
    r1 = preflight(project)
    assert r1.valid is True
    assert cache.exists(), "preflight cache should be written after a green run"
    payload1 = cache.read_text(encoding="utf-8")

    # No intent change → cache hash unchanged across calls.
    r2 = preflight(project)
    assert r2.valid is True
    assert cache.read_text(encoding="utf-8") == payload1

    # Bump the intent's mtime → cache must invalidate and re-validate.
    _bump_mtime(p)
    r3 = preflight(project)
    assert r3.valid is True
    payload3 = cache.read_text(encoding="utf-8")
    assert payload3 != payload1, "cache hash must change when intent mtime changes"


def test_invalid_intent_fails_preflight_after_edit_despite_cache(
    project: Path,
) -> None:
    p = _write(project, "alpha", _VALID_ACTIVE.format(name="alpha", version=1))
    cache = project / ".i2e" / ".preflight_cache.json"

    r1 = preflight(project)
    assert r1.valid is True
    assert cache.exists()

    # Rewrite the intent to be invalid (no evidence and no constraints).
    p.write_text(_NO_ITEMS_ACTIVE.format(name="alpha"), encoding="utf-8")
    _bump_mtime(p)

    r2 = preflight(project)
    assert r2.valid is False
    assert "alpha" in r2.errors
    # Cache must be removed so a stale green result can't mask the failure.
    assert not cache.exists()


def test_tick_result_contract_unchanged(project: Path) -> None:
    """The TickResult fields the orchestrator returns must stay stable —
    the fast-tick-noop work is supposed to change latency only."""
    result = tick(project)
    expected = {
        "tick_id",
        "action",
        "actions_log",
        "report_path",
        "report_link",
        "shippable",
    }
    assert set(result.model_dump().keys()) == expected
    # Same shape on a non-trivial tick path (draft-only project → Shippable).
    _write(project, "wip", _VALID_DRAFT.format(name="wip"))
    result2 = tick(project)
    assert set(result2.model_dump().keys()) == expected
