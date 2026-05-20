# Task: Auto-invocation hook from orchestrator

**Status:** [ ] Pending

**Dependencies:** task-03-view-model, task-04-step-advance (epic 07)

## Context

The orchestrator calls `report.render(root)` after every non-empty tick. This task verifies the wiring is real, end-to-end, and renders the freshness banner correctly.

## Needed from User

None.

## Instructions

1. Confirm `orchestrator.tick` calls `report.render` after writing the tick log (it should, from epic 07 task-04)
2. Add a "freshness" assertion: after `tick`, the mtime of `.i2e/report.html` is >= the mtime of the latest tick log
3. Add `report.render_to_string(root)` for tests that want the HTML without writing to disk
4. Add a regression test in `tests/orchestrator/test_report_invocation.py`:
   - Run a tick that causes evidence to write
   - Assert `.i2e/report.html` exists, is non-empty, and contains the capability's deep-link id

## Acceptance Criteria

- [ ] Orchestrator's `tick` invokes `report.render` exactly once per non-empty tick
- [ ] Report file mtime ≥ tick log mtime
- [ ] Empty (Shippable) ticks do NOT touch the report file (idempotent)
- [ ] Regression test confirms the deep-link id appears in the rendered HTML
