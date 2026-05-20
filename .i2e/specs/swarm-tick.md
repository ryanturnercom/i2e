# Swarm tick — parallel batch execution

The existing `swarm-tick` capability is too large for one develop cycle.
The five sections below break it into independently testable slices,
preserving the original semantics. After each slice ships, the original
`swarm-tick` capability can be retired.

## Section 1: Atomic Worktree Claim

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

## Section 2: Runtime Frontmatter Mirror

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

## Section 3: Batch Tick Planner

Replace one-action-per-tick with one batch of non-conflicting actions
per tick. Pure planning, no I/O. Algorithm: compute the eligible set
via the existing 5-branch tree; topo-sort by `depends_on:` and drop any
capability whose parents are not yet shippable; greedy-select a batch
where no two members' `touches:` globs overlap. Output is an ordered
list of slugs the dispatcher will claim and run in parallel. A
single-active-capability project produces a one-element batch — no
batch-mode overhead, identical to today's behaviour. A `Shippable`
project still produces an empty batch (no-op tick).

## Section 4: Worktree Dispatch and Merge

After the planner produces a batch, the dispatcher acquires a claim per
slug (Section 1), writes `claim.json`, mirrors `runtime:` (Section 2),
and sets up a git worktree of `src/` + `tests/`. It dispatches develop
and evidence in parallel using the Agent tool with
`isolation: worktree`. When the batch finishes, each worktree is merged
back deterministically (alphabetical order). If one merge conflicts the
dispatcher aborts only that capability with a clear error — the others
still land. On success or hard failure the worktree directory is
removed and the `runtime:` mirror cleared, releasing the claim.

## Section 5: Tick Log Sub-Actions

The tick log shape gains `sub_actions: [...]` so a batch tick records
one entry per batch member rather than collapsing into one opaque
string. The legacy `actions: [...]` field stays present and populated
(typically with the batch-level summary line) so existing tick log
readers keep working. The report renderer reads `sub_actions` when
available and falls back to `actions` otherwise.
