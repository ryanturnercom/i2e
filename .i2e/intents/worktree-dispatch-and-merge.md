---
capability: worktree-dispatch-and-merge
created: '2026-05-20'
updated: '2026-05-20'
version: 1
status: active
watcher: '@me'
depends_on:
- batch-tick-planner
touches:
- src/i2e_core/swarm.py
- tests/test_worktree_dispatch_and_merge.py
spec: swarm-tick
spec_section: '4'
---

After the planner produces a batch, the dispatcher acquires a claim per
slug (Section 1), writes `claim.json`, mirrors `runtime:` (Section 2),
and sets up a git worktree of `src/` + `tests/`. It dispatches develop
and evidence in parallel using the Agent tool with
`isolation: worktree`. When the batch finishes, each worktree is merged
back deterministically (alphabetical order). If one merge conflicts the
dispatcher aborts only that capability with a clear error — the others
still land. On success or hard failure the worktree directory is
removed and the `runtime:` mirror cleared, releasing the claim.

## Evidence of success

- id: worktree-dispatch-and-merge-implemented
  type: case
  provider: pytest
  query: tests/test_worktree_dispatch_and_merge.py::test_implemented
  expect: passes
  effort: medium

## Constraints
