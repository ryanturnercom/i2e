---
capability: runtime-frontmatter-mirror
created: '2026-05-20'
updated: '2026-05-21'
version: 1
status: shipped
watcher: '@me'
depends_on:
- atomic-worktree-claim
touches:
- src/i2e_core/swarm.py
- src/i2e_core/intent.py
- tests/test_runtime_frontmatter_mirror.py
spec: swarm-tick
spec_section: '2'
---

`claim.json` is authoritative, but it is also mirrored into the
capability's intent file as a `runtime:` frontmatter block so a quick
`grep -l "^runtime:" .i2e/intents/*.md` answers "what is being worked on
right now." The mirror is written after a successful worktree claim and
removed on release (success or hard failure) and on stale-PID sweep.
Crucially the mirror does NOT participate in the CAS — deleting the
`runtime:` block by hand does not release the lock; only removing the
worktree directory does. This keeps the race-safe primitive separate
from the human-readable surface. Boundary carve-out: the orchestrator
may write the `runtime:` block on an active intent, but no other field.
`status:` is never touched by this path. `i2e-intent` still owns
everything else.

## Evidence of success

- id: runtime-frontmatter-mirror-implemented
  type: case
  provider: pytest
  query: tests/test_runtime_frontmatter_mirror.py::test_implemented
  expect: passes
  effort: medium

## Constraints
