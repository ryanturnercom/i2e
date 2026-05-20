---
capability: i2e-regression
created: '2026-05-20'
updated: '2026-05-20'
version: 1
status: draft
watcher: '@ryan'
---

# `i2e-regression` skill - periodic case re-validation

`shipped` capabilities are not auto-revalidated by the IDEA loop. Their
pytest cases passed once and the orchestrator parks them. Code rot,
dependency upgrades, or external regressions can silently break a
shipped capability and the dashboard won't notice.

Branch 4 of `decide()` handles targets via the `window:` field, but
there is no equivalent for cases. This intent adds a dedicated skill -
`i2e-regression` - that re-runs all case + constraint evidence for every
shipped (and optionally active) capability, on demand or via cadence.

## Behavior

- Inputs: optional `--status shipped|active|all` (default `shipped`),
  optional `--capability <slug>` to scope.
- Action: for each in-scope capability, invoke `evidence_runner.run` over
  cases + constraints only (targets continue to flow through branch 4).
- Outcome: any verdict that flips to `fail`/`unmet`/`trending`:
  - demotes the capability from `shipped` -> `active` (same carve-out as
    `intent-shipped-status`).
  - leaves it in `active` so the next tick picks it up via branches 2/3.
- A run id is written to `.i2e/logs/regressions/<run_id>.yaml` listing
  every capability touched and the deltas.

## Cadence

Cadence is BYO - call directly, schedule via `/schedule`, or wire to CI.
The skill itself has no built-in timer.

## Spec updates required
- Section 4.1: add `i2e-regression` to loop skills.
- Section 9 (Logs): document `.i2e/logs/regressions/`.
- Appendix B: add to the skill index.
- Section 12.7: add this intent to planned-extensions index.

## Depends on

`intent-shipped-status` - regression needs the demotion path to exist.

## Evidence of success

- id: regression-runs-all-cases-for-shipped
  type: case
  provider: pytest
  query: tests/test_i2e_regression.py::test_default_run_revalidates_all_shipped_capabilities
  expect: passes
  effort: medium

- id: regression-respects-status-flag
  type: case
  provider: pytest
  query: tests/test_i2e_regression.py::test_status_flag_filters_to_active_or_all
  expect: passes
  effort: medium

- id: regression-respects-capability-flag
  type: case
  provider: pytest
  query: tests/test_i2e_regression.py::test_capability_flag_scopes_to_single_slug
  expect: passes
  effort: medium

- id: regression-demotes-on-case-failure
  type: case
  provider: pytest
  query: tests/test_i2e_regression.py::test_case_failure_demotes_shipped_back_to_active
  expect: passes
  effort: medium

- id: regression-skips-targets
  type: case
  provider: pytest
  query: tests/test_i2e_regression.py::test_target_items_not_re_evaluated_by_regression
  expect: passes
  effort: medium

- id: regression-writes-log-entry
  type: case
  provider: pytest
  query: tests/test_i2e_regression.py::test_run_writes_log_under_dot_i2e_logs_regressions
  expect: passes
  effort: low

- id: spec-mentions-i2e-regression
  type: case
  provider: pytest
  query: tests/test_i2e_regression.py::test_spec_documents_i2e_regression_in_4_1_and_appendix_b
  expect: passes
  effort: low

## Constraints

- id: regression-does-not-touch-targets
  provider: pytest
  query: tests/test_i2e_regression.py::test_target_verdicts_unchanged_by_regression
  expect: passes
  effort: low

- id: regression-does-not-modify-draft-or-retired
  provider: pytest
  query: tests/test_i2e_regression.py::test_draft_and_retired_capabilities_untouched
  expect: passes
  effort: low
