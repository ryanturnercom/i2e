# Task: Tests for develop flow

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-02-context-loader, task-03-develop-workflow, task-04-idempotency

## Context

Cover all deterministic helpers in develop.py and context.py.

## Needed from User

None.

## Instructions

1. `tests/develop/test_context_loader.py`:
   - Empty context dir returns empty
   - Truncation at `max_chars` preserves document boundaries
2. `tests/develop/test_diff.py`:
   - First run (no prior evidence) ⇒ all items new
   - Same intent + matching `current.yaml` ⇒ no diff
   - Removed item ⇒ shows up in `removed_items`
3. `tests/develop/test_needs_develop.py`:
   - All three branches from the acceptance criteria of task-04
4. `tests/develop/test_paths.py`:
   - Slug-to-package conversion
   - Pytest nodeid → file path extraction

## Acceptance Criteria

- [✓] All develop tests pass via `pytest tests/develop/ -q`
- [✓] Coverage of `i2e_core.develop` and `i2e_core.context` is >85%

## Implementation Notes

- 41 new tests across four files in `tests/develop/`, all green:
  - `test_context_loader.py` (12 tests) — listing, recursion, budget,
    document-boundary truncation, summary headings/first-lines/empty.
  - `test_diff.py` (8 tests) — first run, no-diff, removed items, added
    items after version bump, last_failures from raw.error / raw.output
    / missing raw / passing items.
  - `test_needs_develop.py` (8 tests) — all three needs_develop branches,
    scoped_capabilities for missing-dir, draft, retired, up-to-date.
  - `test_paths.py` (12 tests) — slug-to-package conversion, pytest nodeid
    extraction (with and without ::), non-pytest providers returning None,
    constraint accepted, develop_summary three branches.
- Shared fixtures in `tests/develop/conftest.py`: `develop_project` (bare
  shorten-url) and `develop_project_with_context` (adds the seeded
  ARCHITECTURE.md / DESIGN.md to `.i2e/context/`).
- Coverage post-epic: `i2e_core.develop` 95%, `i2e_core.context` 94%,
  overall `src/i2e_core/` 96%.
