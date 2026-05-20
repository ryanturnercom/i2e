# Task: Tests for each decision branch

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-04-step-advance

## Context

End-to-end orchestrator tests. Build a project state, invoke `tick`, assert the right action ran and the right files moved.

## Needed from User

None.

## Instructions

1. `tests/orchestrator/test_preflight.py`:
   - Valid intents → `preflight().valid == True`
   - Unknown provider in an active intent → `valid == False`, error mentions the capability
   - Draft and retired intents do not block preflight
2. `tests/orchestrator/test_decide.py`:
   - Branch 1: resolved pending exists → `ApplyResolutions`
   - Branch 2: new intent, no current.yaml → `DevelopAndEvidence`
   - Branch 3: current.yaml has trending items with budget → `AdaptThenRetry`
   - Branch 4: target window elapsed → `ReEvaluateItem`
   - Branch 5: all green → `Shippable`
   - Branch 1 wins over branch 2 when both apply
3. `tests/orchestrator/test_tick.py`:
   - Branch 2 happy path: tick produces evidence files, tick log, and report
   - Branch 1: resolved pending applies, file moves to logs/
   - Shippable: no log, no report, exit 0
   - Preflight fail: tick raises `PreflightFailed`
4. `tests/orchestrator/test_cli.py`:
   - `python -m i2e_core.orchestrator` exits 0/1/2 appropriately

## Acceptance Criteria

- [x] All orchestrator tests pass via `pytest tests/orchestrator/ -q`
- [x] Each of the 5 decision branches has at least one positive test
- [x] At least one cross-branch precedence test (branch 1 beats branch 2)
- [x] Coverage of `orchestrator.py` is >85%

## Implementation Notes

- `tests/orchestrator/conftest.py` re-uses the
  evidence/adapt pattern: a `project` fixture, a `write_intent` factory,
  a `write_current_for` factory, and a `patch_providers` fixture that
  patches BOTH `evidence_runner.{load_provider,installed_provider_names}`
  AND `orchestrator.installed_provider_names` so preflight sees the same
  fake-provider universe as the runner.
- `test_preflight.py` (7 tests): valid/invalid intents, draft+retired
  ignored, error aggregation, missing intents dir, `PreflightFailed`
  message rendering.
- `test_decide.py` (16 tests): `parse_window` happy + bad paths, one
  test per branch, plus three precedence tests
  (1>2, 2>3, 3>4) and two negative tests for branch 4 (within window,
  no window field, no last_observed).
- `test_tick.py` (9 tests): Shippable no-op, develop+evidence happy
  path (asserts log file written, render called once, evidence applied),
  apply-resolutions archives the pending file, adapt-retry does not
  escalate when budget remains, adapt escalates when budget exhausted,
  re-evaluate single-item, preflight failure raises `PreflightFailed`,
  tick log file content matches `actions_log`, evidence runner
  exceptions are caught.
- `test_cli.py` (4 tests): `_main` exit codes 0/1/2 + an end-to-end
  `python -m i2e_core.orchestrator` subprocess invocation.
