"""Parallel agent visibility — how many agents are running simultaneously.

The Develop region must make it obvious how many capabilities are in flight
at the same moment, how many distinct agents are running them, and which
IDEA step each one is on.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

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
        f"## Evidence of success\n"
        f"\n"
        f"- id: {name}-case\n"
        f"  type: case\n"
        f"  provider: pytest\n"
        f"  query: q\n"
        f"  expect: passes\n"
        f"  effort: medium\n"
        f"\n"
        f"## Constraints\n"
    )


def _seed_intent(root: Path, name: str) -> None:
    for sub in ("intents", "evidence", "pending", "logs", "context"):
        (root / ".i2e" / sub).mkdir(parents=True, exist_ok=True)
    (root / ".i2e" / "intents" / f"{name}.md").write_text(
        _intent(name), encoding="utf-8"
    )


def _write_claim(root: Path, claim: Claim) -> None:
    d = worktree_dir(root, claim.slug)
    d.mkdir(parents=True, exist_ok=True)
    (d / "claim.json").write_text(
        json.dumps(claim.model_dump(mode="json"), indent=2), encoding="utf-8"
    )


def test_implemented(tmp_path: Path) -> None:
    # Three capabilities, three different agents, three different steps —
    # the worst-case visibility test.
    for s in ("alpha", "bravo", "charlie", "delta"):
        _seed_intent(tmp_path, s)

    alive_pid = os.getpid()
    base_ts = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)
    for slug, step, agent in [
        ("alpha", "develop", "agent-1"),
        ("bravo", "evidence", "agent-2"),
        ("charlie", "develop", "agent-3"),  # same step as alpha — parallel develop
        ("delta", "adapt", "agent-2"),       # agent-2 holds two claims simultaneously
    ]:
        _write_claim(
            tmp_path,
            Claim(
                slug=slug,
                agent_id=agent,
                pid=alive_pid,
                tick_id=f"2026-05-20-tk{slug[:3]}",
                step=step,  # type: ignore[arg-type]
                started_at=base_ts,
                progress=f"working on {slug}",
            ),
        )

    # --- view model carries the parallelism roll-up ------------------------
    vm = build_view_model(tmp_path)
    p = vm.parallelism
    assert p.parallel_count == 4  # four live claims
    # agent-1, agent-2, agent-3 → three distinct agents (agent-2 has 2 claims)
    assert p.distinct_agents == 3
    # develop=2, evidence=1, adapt=1
    assert p.by_step == {"develop": 2, "evidence": 1, "adapt": 1}

    # --- HTML surfaces the metrics in the Develop section ------------------
    html = render_to_string(tmp_path)
    assert 'id="parallelism-summary"' in html
    assert "4</strong> in flight" in html
    assert "3</strong> agents" in html
    # Step breakdown chip group shows each running step + its count.
    assert 'id="parallelism-by-step"' in html
    assert "develop: 2" in html
    assert "evidence: 1" in html
    assert "adapt: 1" in html

    # Every claim still gets its own row, anchored for deep-linking.
    for slug in ("alpha", "bravo", "charlie", "delta"):
        assert f'id="inflight/{slug}"' in html

    # The parallelism metrics live inside the Develop stage section.
    develop_start = html.index('id="stage-develop"')
    evidence_start = html.index('id="stage-evidence"')
    assert develop_start < html.index('id="parallelism-summary"') < evidence_start

    # --- A stale claim does NOT inflate the parallelism count --------------
    _seed_intent(tmp_path, "echo")
    _write_claim(
        tmp_path,
        Claim(
            slug="echo",
            agent_id="agent-dead",
            pid=999_998,  # dead pid
            tick_id="2026-05-20-tkecho",
            step="develop",
            started_at=base_ts,
            progress="",
        ),
    )
    vm2 = build_view_model(tmp_path)
    assert vm2.parallelism.parallel_count == 4  # echo doesn't count
    assert "agent-dead" not in {a for a in [r.agent_id for r in vm2.in_flight if r.alive]}
    # But the stale row is still rendered for awareness.
    html2 = render_to_string(tmp_path)
    assert 'id="inflight/echo"' in html2
