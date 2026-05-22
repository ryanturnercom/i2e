"""Live in-flight status panel — surfaces active worktree claims.

A watcher should land on the report and immediately see which capabilities
are being worked on right now, by which agent, and on which step of the
loop. The panel reads from ``.i2e/worktrees/<slug>/claim.json``.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from i2e_core.evidence import CurrentEvidence, ItemVerdict, write_current
from i2e_core.pending import PendingFile, write_pending
from i2e_core.report import build_view_model, render_to_string
from i2e_core.swarm import Claim, worktree_dir


def _intent(name: str) -> str:
    return (
        f"---\n"
        f"capability: {name}\n"
        f"created: '2026-05-20'\n"
        f"updated: '2026-05-20'\n"
        f"version: 1\n"
        f"status: active\n"
        f"watcher: '@me'\n"
        f"---\n"
        f"\n"
        f"# {name}\n"
        f"\n"
        f"## Evidence of success\n"
        f"\n"
        f"- id: {name}-case\n"
        f"  type: case\n"
        f"  provider: pytest\n"
        f"  query: tests/test_{name.replace('-', '_')}.py::test_x\n"
        f"  expect: passes\n"
        f"  effort: medium\n"
        f"\n"
        f"## Constraints\n"
    )


def _seed_intent(root: Path, slug: str) -> None:
    for sub in ("intents", "evidence", "pending", "logs", "context"):
        (root / ".i2e" / sub).mkdir(parents=True, exist_ok=True)
    (root / ".i2e" / "intents" / f"{slug}.md").write_text(
        _intent(slug), encoding="utf-8"
    )
    cur = CurrentEvidence(
        capability=slug,
        last_run="2026-05-20-aaa000",
        intent_version=1,
        items={
            f"{slug}-case": ItemVerdict(
                verdict="pass",
                attempts_used=0,
                last_observed=datetime.now(timezone.utc),
            )
        },
    )
    write_current(root, cur)


def _write_claim(root: Path, claim: Claim) -> None:
    d = worktree_dir(root, claim.slug)
    d.mkdir(parents=True, exist_ok=True)
    (d / "claim.json").write_text(
        json.dumps(claim.model_dump(mode="json"), indent=2), encoding="utf-8"
    )


def test_implemented(tmp_path: Path) -> None:
    # --- 1. With no claims, panel renders an empty state. -------------------
    _seed_intent(tmp_path, "alpha")
    vm = build_view_model(tmp_path)
    assert vm.in_flight == []
    html = render_to_string(tmp_path)
    assert "Live status" in html
    assert 'id="live-status"' in html
    assert "Nothing in flight" in html

    # --- 2. One live claim → row appears with capability, step, agent ------
    live_claim = Claim(
        slug="alpha",
        agent_id="agent-aaaa",
        session_id="sess-1",
        pid=os.getpid(),  # this process is alive → row not flagged stale
        tick_id="2026-05-20-abc123",
        step="develop",
        started_at=datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc),
        progress="writing src/alpha/__init__.py",
    )
    _write_claim(tmp_path, live_claim)

    vm = build_view_model(tmp_path)
    assert len(vm.in_flight) == 1
    row = vm.in_flight[0]
    assert row.slug == "alpha"
    assert row.step == "develop"
    assert row.agent_id == "agent-aaaa"
    assert row.alive is True
    assert "writing src/alpha" in row.progress

    html = render_to_string(tmp_path)
    assert 'id="inflight/alpha"' in html
    assert "agent-aaaa" in html
    assert "step-develop" in html  # step pill class
    assert "writing src/alpha" in html
    # Link from the in-flight row to the capability card.
    assert 'href="#cap/alpha"' in html
    # Live count appears in the summary line.
    assert "1</strong> in flight" in html

    # --- 3. A claim with a dead PID is shown but marked stale --------------
    _seed_intent(tmp_path, "bravo")
    dead_claim = Claim(
        slug="bravo",
        agent_id="agent-bbbb",
        pid=999_999,  # very unlikely to be a real PID
        tick_id="2026-05-20-def456",
        step="evidence",
        started_at=datetime(2026, 5, 20, 11, 0, 0, tzinfo=timezone.utc),
        progress="",
    )
    _write_claim(tmp_path, dead_claim)

    vm = build_view_model(tmp_path)
    assert len(vm.in_flight) == 2
    by_slug = {row.slug: row for row in vm.in_flight}
    assert by_slug["bravo"].alive is False
    assert by_slug["alpha"].alive is True

    html = render_to_string(tmp_path)
    assert "live-row stale" in html  # bravo row carries the stale class
    assert "stale-tag" in html

    # --- 4. Pending count is also surfaced in the live summary -------------
    pf = PendingFile(
        status="open",
        kind="human_evaluation",
        capability="alpha",
        item_id="alpha-case",
        asked_at=datetime(2026, 5, 20, 13, 0, 0, tzinfo=timezone.utc),
        ask="Looks good?",
        verdict_options=["yes", "no"],
    )
    write_pending(tmp_path, pf)
    html = render_to_string(tmp_path)
    assert "1</strong> awaiting human" in html

    # --- 5. Sorting is deterministic by (slug, started_at) -----------------
    slugs = [r.slug for r in build_view_model(tmp_path).in_flight]
    assert slugs == sorted(slugs)
