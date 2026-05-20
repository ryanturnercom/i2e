---
name: i2e
description: Orchestrator. Runs a preflight scan and advances the project by exactly one step using the IDEA loop decision tree. Auto-invokes i2e-report after any state-changing tick.
license: Apache-2.0
metadata:
  tier: loop
  version: "0.1.0"
---

# i2e

## When to use
- A human says "run i2e" / "tick the loop"
- A scheduler fires (`/schedule` routine, OS scheduler)

## Workflow
1. **Preflight** (`i2e_core.orchestrator.preflight(root)`):
   - Re-run forced-evidence validation across all active intents
   - Halt the tick with a clear error if any intent is invalid (`i2e-intent` is the fix)
2. **Decide** (`i2e_core.orchestrator.decide(root)`):
   - Returns the first matching action from the 5-branch tree:
     1. Resolved pending → `i2e_core.adapt.apply_resolutions`
     2. Stale develop (intent version > current's recorded version) → `i2e-develop` then `i2e-evidence`
     3. Trending/unmet items with budget → `i2e-adapt` → `i2e-develop` + `i2e-evidence`
     4. Target window elapsed → `i2e-evidence` (single item)
     5. All green → mark shippable; no-op
3. **Execute** the action; collect a list of action strings
4. **Tick log**: if any actions occurred, `tick_log.write_tick`
5. **Report**: ALWAYS call `i2e_core.report.render(root)` if anything changed

## Boundaries
- READ: all of `.i2e/`, `src/`, `tests/`
- WRITE: `.i2e/logs/**`, `.i2e/report.html`, plus whatever the dispatched skill writes
- NEVER WRITE DIRECTLY: `.i2e/intents/**`, `.i2e/evidence/**`, `src/**`, `tests/**` (always via a downstream skill)

## Exit codes (CLI invocation)
- 0: tick completed (regardless of green/yellow/red — that's reflected in current.yaml)
- 1: preflight failed
- 2: an executing skill raised
