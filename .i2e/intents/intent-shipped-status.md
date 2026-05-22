---
capability: intent-shipped-status
created: '2026-05-20'
updated: '2026-05-21'
version: 1
status: shipped
watcher: '@ryan'
---

# `shipped` status for completed capabilities

Today `status:` is `draft` | `active` | `retired`. A capability that
reaches all-green stays `active` forever, no-opping on every tick. There
is no slot for "completed and verified" - the dashboard cannot
distinguish work-in-progress from done.

Add a fourth state: `shipped`.

## State semantics

| State    | Orchestrator behavior                                |
|----------|------------------------------------------------------|
| draft    | preflight + decide both ignore                       |
| active   | full IDEA loop applies                               |
| shipped  | branches 1-3 skipped; branch 4 (target window) still |
|          | applies for periodic re-evaluation                   |
| retired  | tombstone; ignored                                   |

## Promotion: `active` -> `shipped`

**Automatic.** When `current.yaml` reports every verdict in `{pass, met}`
for a tick, the orchestrator auto-promotes. No human gate. The
orchestrator does this through a narrow carve-out on intent frontmatter,
same mechanism as the `runtime:` mirror in `swarm-tick`.

## Demotion: `shipped` -> `active`

Two paths only:
1. **Auto via branch 4**: a target's `window:` elapses, evidence re-runs,
   verdict regresses to `unmet`/`trending`/`fail` -> orchestrator demotes
   to `active`. Next tick proceeds normally via branches 2/3.
2. **Manual via `i2e-intent`**: human flip is always allowed.

`Case` (pytest) verdicts are NOT re-run on shipped capabilities by this
intent. A future `i2e-regression` skill (see related draft) will handle
periodic case re-validation.

## Report

The dashboard renders shipped capabilities in a separate "Shipped (N)"
section with green pills, distinct from the active worklist. The
top-banner "Shippable" badge still reflects the latest tick's
`Shippable` action; the shipped section is the persistent record.

## Spec updates required
- Section 2.1: add `shipped` to the status enum.
- Section 6.1: document the auto-promote/auto-demote rules in the
  decision tree.
- Section 8 (Dashboard/report): describe the Shipped section.
- Section 12.6: add this intent to the planned-extensions index.

## Evidence of success

- id: auto-promotes-when-all-green
  type: case
  provider: pytest
  query: tests/test_shipped_status.py::test_capability_auto_promotes_when_all_verdicts_pass_or_met
  expect: passes
  effort: medium

- id: does-not-promote-with-failing-verdict
  type: case
  provider: pytest
  query: tests/test_shipped_status.py::test_capability_stays_active_with_any_non_green_verdict
  expect: passes
  effort: medium

- id: shipped-skipped-by-branch-2
  type: case
  provider: pytest
  query: tests/test_shipped_status.py::test_branch2_does_not_pick_shipped_capability_for_develop
  expect: passes
  effort: medium

- id: shipped-skipped-by-branch-3
  type: case
  provider: pytest
  query: tests/test_shipped_status.py::test_branch3_does_not_pick_shipped_capability_for_adapt
  expect: passes
  effort: medium

- id: shipped-allows-branch-4
  type: case
  provider: pytest
  query: tests/test_shipped_status.py::test_branch4_target_window_still_fires_for_shipped
  expect: passes
  effort: medium

- id: regression-demotes-via-branch-4
  type: case
  provider: pytest
  query: tests/test_shipped_status.py::test_target_regression_demotes_shipped_to_active
  expect: passes
  effort: medium

- id: manual-demotion-via-intent-skill
  type: case
  provider: pytest
  query: tests/test_shipped_status.py::test_i2e_intent_can_flip_shipped_to_active
  expect: passes
  effort: medium

- id: report-renders-shipped-section
  type: case
  provider: pytest
  query: tests/test_shipped_status.py::test_report_renders_shipped_capabilities_in_their_own_section
  expect: passes
  effort: medium

- id: spec-mentions-shipped-status
  type: case
  provider: pytest
  query: tests/test_shipped_status.py::test_spec_documents_shipped_state_in_2_1_and_6_1
  expect: passes
  effort: low

## Constraints

- id: existing-three-states-unchanged
  provider: pytest
  query: tests/test_shipped_status.py::test_draft_active_retired_behavior_unchanged
  expect: passes
  effort: low

- id: orchestrator-only-writes-status-on-promote-demote
  provider: pytest
  query: tests/test_shipped_status.py::test_orchestrator_status_carve_out_scoped_to_shipped_transitions
  expect: passes
  effort: low
