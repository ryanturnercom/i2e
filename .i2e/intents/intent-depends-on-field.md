---
capability: intent-depends-on-field
created: '2026-05-20'
updated: '2026-05-21'
version: 1
status: shipped
watcher: '@ryan'
---

# `depends_on:` field for capability ordering

`orchestrator.decide()` currently breaks branch-2 ties alphabetically. With
multi-capability programs (a PRD decomposed into A -> B -> C), the
orchestrator has no way to know B's tests will fail until A is developed.

Add `depends_on: [slug, ...]` to capability frontmatter. Validation rules:
referenced slugs must exist; cycles are rejected at preflight. `decide()`
performs a topological sort over the eligible set before the alphabetical
tiebreaker. A child never fires before its parent is in shippable state.

## Spec updates required
- Section 2.1 (Intent file): add `depends_on:` to frontmatter schema.
- Section 5 (Forced-evidence rules): add depends_on graph must be acyclic.
- Section 6.1: note that branch 2 respects depends_on before alphabetical.

## Evidence of success

- id: depends-on-round-trips
  type: case
  provider: pytest
  query: tests/test_depends_on.py::test_depends_on_field_round_trips_through_intent_io
  expect: passes
  effort: low

- id: decide-respects-dep-order
  type: case
  provider: pytest
  query: tests/test_depends_on.py::test_branch2_picks_parent_before_child
  expect: passes
  effort: medium

- id: cycle-rejected-by-preflight
  type: case
  provider: pytest
  query: tests/test_depends_on.py::test_preflight_rejects_dependency_cycle
  expect: passes
  effort: medium

- id: unknown-dep-rejected
  type: case
  provider: pytest
  query: tests/test_depends_on.py::test_preflight_rejects_unknown_dependency
  expect: passes
  effort: medium

- id: spec-mentions-depends-on
  type: case
  provider: pytest
  query: tests/test_depends_on.py::test_spec_documents_depends_on_field
  expect: passes
  effort: low

## Constraints

- id: no-depends-on-behaves-as-today
  provider: pytest
  query: tests/test_depends_on.py::test_capabilities_without_depends_on_unchanged
  expect: passes
  effort: low
