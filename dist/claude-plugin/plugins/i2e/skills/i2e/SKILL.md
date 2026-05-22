---
name: i2e
description: Orchestrator. Runs a preflight scan and keeps ticking the IDEA loop until the project is Shippable (or no further progress is possible). Auto-invokes i2e-report after any state-changing tick.
license: Apache-2.0
metadata:
  tier: loop
  version: "0.2.0"
---

# i2e

## When to use
- A human says "run i2e" / "tick the loop"
- A scheduler fires (`/schedule` routine, OS scheduler)

## Loop behaviour
A single `/i2e` invocation keeps running ticks back-to-back until one of these
terminal conditions is hit:

1. `decide(root)` returns `Shippable` → success, stop.
2. `preflight(root)` reports an invalid intent → halt with the error so the
   operator can run `i2e-intent` to fix it.
3. A safety guard trips (see **Stop conditions** below) → stop and report.

The Python `orchestrator.tick()` is still a single-step primitive (the CLI
`python -m i2e_core.orchestrator` and scheduler integration both rely on that
contract). The loop lives in **this skill** so the human-facing `/i2e`
experience drives the project to a steady state in one go.

## Workflow (per iteration)
1. **Preflight** (`i2e_core.orchestrator.preflight(root)`):
   - Re-run forced-evidence validation across all active intents
   - On failure: stop the loop and surface the error (`i2e-intent` is the fix)
2. **Decide** (`i2e_core.orchestrator.decide(root)`):
   - Returns the first matching action from the 5-branch tree:
     1. Resolved pending → `i2e_core.adapt.apply_resolutions`
     2. Stale develop (intent version > current's recorded version) → `i2e-develop` then `i2e-evidence`
     3. Trending/unmet items with budget → `i2e-adapt` → `i2e-develop` + `i2e-evidence`
     4. Target window elapsed → `i2e-evidence` (single item)
     5. All green → mark shippable; no-op
3. **Execute** the action; collect a list of action strings. For
   `DevelopAndEvidence`, invoke the `i2e-develop` skill so real code is
   written before `tick()` runs evidence on the next call.
4. **Tick log**: if any actions occurred, `tick_log.write_tick`
5. **Report**: call `i2e_core.report.render(root)` after any state-changing
   tick so `.i2e/report.html` stays fresh as the loop progresses.
6. **Loop or stop**:
   - If the action was `Shippable` → stop, report final state.
   - Otherwise → go back to step 1 for the next tick.

The cheapest way to drive iterations is `i2e_core.orchestrator.tick(root)`,
which already does preflight + decide + execute + log + report internally.
Call it in a loop, inspect the returned `TickResult`, and break when
`result.shippable` is True. For the `DevelopAndEvidence` branch, invoke
`i2e-develop` between ticks so the next tick's evidence runs against the
newly written code.

## Stop conditions (safety guards)
End the loop early — do not keep ticking — when any of these hold:

- `result.shippable` is True (the happy path).
- `preflight` raises `PreflightFailed` (operator must fix the intent).
- An executing skill raises an unrecoverable exception.
- The same action+capability pair has been chosen twice in a row with an
  identical `actions_log` — the loop is no longer making progress (e.g. a
  flaky external provider, an exhausted retry budget). Stop and surface the
  state so the human can intervene.
- A hard ceiling of **20 iterations** in a single `/i2e` invocation, to bound
  runaway loops. Surface a clear message if hit.

When you stop, summarise: how many ticks ran, the final action, and the
report path so the human can pick up where the loop left off.

## The localhost report server
`i2e` renders the static `.i2e/report.html` on every state-changing tick —
that file always works on its own (just open it). `i2e` never starts, stops,
or restarts the localhost live server: the server is operator-owned.

If the user wants live auto-refreshing updates while the loop runs, tell them
to run `bash .i2e/start.sh` in their own terminal. Do not run it for them,
and never kill a server they started. (See the `i2e-serve` skill.)

## Boundaries
- READ: all of `.i2e/`, `src/`, `tests/`
- WRITE: `.i2e/logs/**`, `.i2e/report.html`, the first-run `.i2e/` scaffold (layout dirs + start/stop/restart scripts, written by `init_project` at the top of each `tick`), plus whatever the dispatched skill writes
- NEVER WRITE DIRECTLY: `.i2e/intents/**`, `.i2e/evidence/**`, `src/**`, `tests/**` (always via a downstream skill)
- NEVER start, stop, or restart the localhost report server — operator-owned

## Exit codes (CLI invocation — `python -m i2e_core.orchestrator`)
The CLI still runs **exactly one tick** (single-step contract for schedulers).
- 0: tick completed (regardless of green/yellow/red — that's reflected in current.yaml)
- 1: preflight failed
- 2: an executing skill raised
