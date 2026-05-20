# Task: Tests for the evidence runner

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-02-provider-invocation, task-03-evidence-collection, task-04-async-pending

## Context

Comprehensive coverage for the runner — happy paths, provider exceptions, async lifecycle, idempotency.

## Needed from User

None.

## Instructions

1. `tests/evidence/test_runner_happy.py`:
   - Capability with one passing pytest case ⇒ summary `{pass:1}`, `current.yaml` + `runs/<id>.yaml` exist
   - Capability with one failing case ⇒ summary `{fail:1}`, `attempts_used=1`
2. `tests/evidence/test_runner_exceptions.py`:
   - Provider raises ⇒ item recorded as `fail` with `raw.error`, other items still run
3. `tests/evidence/test_runner_async.py`:
   - First run on a `provider: human` item ⇒ pending file written, verdict `awaiting_human`
   - Re-run while pending open ⇒ no new file, verdict unchanged
   - Resolve pending (`status: resolved`, `resolution: yes`) + re-run ⇒ archive, verdict `pass`
4. `tests/evidence/test_runner_idempotent.py`:
   - Re-running with same intent version produces a NEW run snapshot but a `current.yaml` whose `last_run` updates
5. `tests/evidence/test_reconcile.py`:
   - `reconcile` reproduces `current.yaml` from the latest snapshot

## Acceptance Criteria

- [x] All evidence tests pass via `pytest tests/evidence/ -q`
- [x] Coverage of `evidence_runner` and `evidence` is >85%
- [x] Test runtime stays under 60s (pytest subprocess is the bottleneck — use tiny fixture tests)

## Implementation Notes

- Created `tests/evidence/` with:
  - `__init__.py` — package marker
  - `conftest.py` — shared fixtures: `project` (minimal `.i2e/`
    skeleton), `write_intent` (factory for writing a minimal valid
    intent file), `patch_providers` (monkeypatches
    `evidence_runner.load_provider` and `installed_provider_names` to
    install `FakeProvider` instances)
  - `test_runner_happy.py` — passing case, failing case, pass+fail
    summary alias round-trip, constraints sharing the loop,
    `attempts_used` reset semantics on pass, `only_items` carry-over,
    target/met verdict
  - `test_runner_exceptions.py` — provider raises is captured as
    `fail` with `raw.error`; one bad provider doesn't crash other
    items; validation errors propagate (don't get swallowed)
  - `test_runner_async.py` — first run writes pending + records
    `awaiting_human`, second run while open keeps verdict (no new
    file), resolved-yes becomes pass + archives, resolved-no becomes
    fail. Also unit tests for `resolve_to_verdict` covering yes /
    partial / open / escalation / unknown branches.
  - `test_runner_idempotent.py` — two runs make two snapshots with the
    same intent version, forced run-id collision raises
    `FileExistsError`, current.yaml verdicts match the latest
    snapshot byte-for-byte
  - `test_reconcile.py` — `reconcile` reproduces the same
    CurrentEvidence from the latest snapshot, raises when no
    snapshots exist, and picks the most recent run when multiple
    same-day runs exist
  - `test_cli.py` — `_main` exits 0 on success and prints JSON; exits
    1 on validation failure and writes a stderr message
- All tests use `FakeProvider` via `patch_providers`; no real pytest
  subprocesses are spawned in epic 05 (that's epic 02's domain).
- Result: 27 evidence tests pass in ~0.3s. Whole suite (183 tests)
  passes in ~1.2s. Coverage 96% overall; `evidence_runner` 93%,
  `pending` 98%, `evidence` 100%. Uncovered lines are defensive
  fallbacks (pending/ dir missing during a FileExistsError, generic
  catch-all on `to_item_verdict`).
