---
capability: atomic-worktree-claim
created: '2026-05-20'
updated: '2026-05-21'
version: 1
status: shipped
watcher: '@me'
touches:
- src/i2e_core/swarm.py
- tests/test_atomic_worktree_claim.py
spec: swarm-tick
spec_section: '1'
---

The claim primitive: `.i2e/worktrees/<slug>/` directory existence IS the
lock. Acquisition is `os.makedirs(path, exist_ok=False)` — atomic CAS
across POSIX and Windows. Inside the worktree, a `claim.json` file
records `agent_id` (UUID per orchestrator process), `session_id`
(optional parent identifier such as a Claude Code session), `pid`,
`tick_id`, `step` (one of develop / evidence / adapt), `started_at`
ISO-8601 UTC, and a free-text `progress` field updated as work
proceeds. Liveness handling: on `FileExistsError`, read `claim.json`.
If the recorded `pid` is alive the claim stands; if dead, the worktree
directory is removed and the mkdir is retried. This is the load-bearing
race-safe primitive; everything else builds on it.

## Evidence of success

- id: atomic-worktree-claim-implemented
  type: case
  provider: pytest
  query: tests/test_atomic_worktree_claim.py::test_implemented
  expect: passes
  effort: medium

## Constraints
