---
name: i2e-watch
description: Watch .i2e/intents/ for changes and dispatch develop + evidence for each changed capability that is ready for dev, capped at watch.max_concurrent.
license: Apache-2.0
metadata:
  tier: loop
  version: "0.1.0"
  optional: true
---

# i2e-watch

A continuous, event-driven front door to the IDEA loop. Instead of the
operator running `/i2e` after every intent edit, `i2e-watch` blocks on
`.i2e/intents/` and, the moment an intent file changes, dispatches
`i2e-develop` + `i2e-evidence` for the capabilities that changed and are
ready for dev — up to `watch.max_concurrent` at a time.

It is the same work `/i2e` does for a `DevelopAndEvidence` action, but
triggered by a file change rather than a manual tick or a scheduler
cadence. `i2e-watch` complements `/i2e` (and the BYO scheduler); it does
not replace them.

## When to use
- The operator wants intents to build themselves as they are authored —
  edit `.i2e/intents/<cap>.md`, bump `version`, save, and watch it develop.
- An active editing session where many intents are changing and a per-edit
  `/i2e` is tedious.

Not for cadence-based re-validation of shipped work — that is `i2e-regression`
on a `/schedule`. `i2e-watch` only ever acts on a *change*.

## How it works

The Python core (`i2e_core.watch`) is the deterministic half: it watches
files and plans batches. This skill is the loop and the dispatch.

The watcher triggers off the intent **`version`**, not the file mtime. A
capability is dispatched only when its `version` is greater than the version
the watcher last dispatched (tracked in `.i2e/.watch_state.json`). This is
deliberate:

- The orchestrator rewrites intent files mid-develop (the `runtime:`
  mirror). A mtime watcher would treat that as a fresh edit and loop. A
  `runtime:` write never bumps `version`, so it never re-triggers.
- A develop that fails does not re-trigger either — its `version` is already
  recorded. To retry, the human re-bumps the intent. Explicit, no thrash.

So the contract for the operator is the same as the worked example in the
spec: **bump `version` (and `updated`) in the frontmatter** to ask the loop
to act.

## Workflow

1. **Announce.** Run `python -m i2e_core.watch plan --root .` and report
   the current batch to the user: "Watching `.i2e/intents/` — N
   capabilities pending, M will dispatch on the next change. Edit and save
   an intent (bump `version`) to trigger develop. Interrupt to stop."

2. **Loop.** Repeat until the user interrupts:

   a. **Wait for a batch.** Run
      `python -m i2e_core.watch next --root . --timeout 540`. This blocks
      until a changed-and-ready batch exists, or 540s elapse. Keep the
      timeout at 540 — under the Bash tool's 10-minute ceiling — and treat
      a timeout as a no-op: a missed filesystem event self-heals because
      `next` re-scans on every call.

   b. **Parse** the one JSON line: `{batch, remaining, max_concurrent,
      reason, timed_out}`. If `timed_out` is true, go back to (a).

   c. **Preflight.** Run `i2e_core.orchestrator.preflight(root)`. If it
      reports an invalid intent, surface the error and go back to (a) —
      do not dispatch against a broken intent. The operator fixes it via
      `i2e-intent`, which is itself a change that wakes the watcher.

   d. **Dispatch the batch concurrently.** `batch` is already capped at
      `watch.max_concurrent` and free of `touches:` conflicts, so dispatch
      every slug in it in parallel. For each slug, run the same
      develop+evidence flow `i2e` runs for a `DevelopAndEvidence` action:
      - `i2e_core.swarm.acquire_claim(root, slug, tick_id=..., step="develop")`
        so `/workers` shows it in flight and a concurrent `/i2e` skips it.
      - Invoke **`i2e-develop`** for that capability (one sub-agent per
        slug, via the Agent tool, all dispatched in a single message so
        they run concurrently).
      - Run evidence: `i2e_core.evidence_runner.run(root, slug)`.
      - Auto-promote to `shipped` if every verdict is green
        (`i2e_core.orchestrator._all_green`), then
        `i2e_core.swarm.release_claim(root, slug)`.

   e. **Log + report.** Write one tick log entry for the batch
      (`i2e_core.tick_log.write_tick`) and refresh the dashboard
      (`i2e_core.report.render(root)`).

   f. **Drain.** If `remaining` is non-empty, loop back to (a)
      immediately — the next `next` call returns the remainder without
      waiting (they are over-cap triggers, not yet recorded).

## Concurrency cap
`watch.max_concurrent` in `.i2e/config.yaml` (default **4**) caps how many
capabilities one cycle develops in parallel. The planner enforces it; the
skill never dispatches more than one `batch` at a time. Triggers beyond the
cap wait in `remaining` and ride the next loop.

## Stop conditions
This skill loops until the user interrupts it. Stop early and report when:
- An executing skill raises an unrecoverable exception.
- `python -m i2e_core.watch next` fails repeatedly (the project root or
  `.i2e/` is gone).
Preflight failure is **not** a stop condition — surface it and keep
watching; the fix is itself a change.

## Boundaries
- READ: all of `.i2e/`, `src/`, `tests/`
- WRITE: `.i2e/.watch_state.json` (via `i2e_core.watch`), `.i2e/logs/**`,
  `.i2e/report.html`, plus whatever the dispatched `i2e-develop` /
  `i2e-evidence` skills write (`src/**`, `tests/**`, `.i2e/evidence/**`)
- NEVER WRITE DIRECTLY: `.i2e/intents/**`, `src/**`, `tests/**`,
  `.i2e/evidence/**` (always via a downstream skill)
- NEVER start, stop, or restart the localhost report server — operator-owned

## Forbidden
- Dispatching a capability with no `version` bump — the watcher gates on
  `version`; respect it rather than working around it.
- Exceeding `watch.max_concurrent` — dispatch one planner batch at a time.
- Editing intent files — that is `i2e-intent`'s job.
- Re-running shipped capabilities on a cadence — that is `i2e-regression`.

## CLI

```bash
python -m i2e_core.watch plan --root .                 # batch now (no wait)
python -m i2e_core.watch next --root . --timeout 540   # block for a batch
python -m i2e_core.watch next --root . --max 2         # override the cap
```

## Python helpers (the deterministic core)
- `i2e_core.watch.plan(root, max_concurrent=None) -> WatchBatch`
- `i2e_core.watch.next_batch(root, max_concurrent=None, timeout=None) -> WatchBatch`
- `i2e_core.watch.watch_state_path(root) -> Path`
- `i2e_core.orchestrator.preflight(root) -> PreflightResult`
- `i2e_core.evidence_runner.run(root, capability) -> RunSummary`
- `i2e_core.swarm.acquire_claim / release_claim`
- `i2e_core.tick_log.write_tick`
- `i2e_core.report.render(root) -> Path`
