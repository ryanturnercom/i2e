---
capability: report-rename-attempts-to-retries
created: '2026-05-20'
updated: '2026-05-20'
version: 1
status: draft
watcher: '@ryan'
---

# Report label: rename "attempts" → "retries"

The report template shows `N/M attempts` next to each item
(`report.html.j2:175`), but the underlying counter (`attempts_used` in
`ItemVerdict`) is only incremented for `fail`/`unmet`/`trending` — it tracks
consumed *retry budget*, not total runs (see `provider/contract.py:104`).
A passing item shows `0/6 attempts`, which reads as "never ran" but actually
means "passed without burning any retries." Rename the user-facing label to
`retries`.

## Scope

1. `src/i2e_core/report/templates/report.html.j2` — change the literal text
   `attempts` to `retries` in the item meta line.
2. **Leave the persisted field name `attempts_used` alone** on `ItemVerdict`.
   Renaming it would invalidate every existing `current.yaml` and run
   snapshot on disk — not worth the churn for a label fix.
3. `ItemView.attempts_used` / `max_attempts` in `view_model.py` can stay too,
   since they are internal to the renderer.

## Out of scope

- Changing increment semantics (still: pass/met/awaiting → no bump;
  fail/unmet/trending → bump).
- Changing the per-effort-tier budgets in `.i2e/config.yaml`.

## Evidence of success

- id: report-shows-retries-label
  type: case
  provider: pytest
  query: tests/test_report_retries_label.py::test_rendered_report_uses_retries_label
  expect: passes
  effort: low

- id: current-yaml-field-unchanged
  type: case
  provider: pytest
  query: tests/test_report_retries_label.py::test_persisted_attempts_used_field_name_unchanged
  expect: passes
  effort: low

## Constraints

- id: report-renders-without-error
  provider: pytest
  query: tests/test_report_retries_label.py::test_report_renders_without_template_error
  expect: passes
  effort: low
