# Task: Tests for budgets, escalation, resolution

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-02-budget-tracker, task-03-pending-generator, task-04-resolution-applier, task-05-tick-log

## Context

Exhaustive coverage of adapt — this is the loop's brain, so regressions here are loud failures.

## Needed from User

None.

## Instructions

1. `tests/adapt/test_plan.py`:
   - All 4 tier+type combinations on each verdict (pass/fail/met/unmet/trending/awaiting_human)
   - Lazy tier escalates on first failure
   - Items with open escalations are excluded from `escalations` list (idempotent)
2. `tests/adapt/test_escalate.py`:
   - Writes a well-formed pending file
   - Includes last 3 attempts when tick log history is available
   - Second call for same item raises FileExistsError
3. `tests/adapt/test_apply_resolutions.py`:
   - Each of the 4 resolution choices applied correctly
   - Option 1 without new expect raises
   - Pending file moves from pending/ to logs/
   - Option 3 bumps intent version
4. `tests/adapt/test_tick_log.py`:
   - Empty actions ⇒ no file
   - Non-empty ⇒ immutable file
   - `changes_since` returns last N entries

## Acceptance Criteria

- [x] All adapt tests pass via `pytest tests/adapt/ -q`
- [x] Coverage of `adapt.py` and `tick_log.py` is >85%
- [x] At least one integration test that runs `plan` → `escalate` → `apply_resolutions` end-to-end

## Implementation Notes

- 37 new tests under `tests/adapt/` (`test_plan.py`, `test_escalate.py`,
  `test_apply_resolutions.py`, `test_tick_log.py`) — all green.
- Shared `tests/adapt/conftest.py` provides `project`, `write_intent`,
  `write_current_for`, and `write_run_for` factory fixtures.
- Coverage on the new modules:
  - `adapt.py`: 85%
  - `tick_log.py`: 95%
- Tests cover every tier/type combination, the lazy first-failure path,
  every resolution choice (including option 1's missing-new-expect error
  path), parser permissiveness, and `changes_since` truncation.
- `test_end_to_end_plan_escalate_apply` is the required integration test:
  `plan` flags the item → `escalate` writes the pending file → human
  resolves it → `apply_resolutions` mutates the intent and archives the
  pending file.
