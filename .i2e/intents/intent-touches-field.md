---
capability: intent-touches-field
created: '2026-05-20'
updated: '2026-05-21'
version: 1
status: shipped
watcher: '@ryan'
---

# `touches:` field for parallel scheduling

To safely fan out work across capabilities, the scheduler needs to know
which file paths each capability writes. Today develop can edit any file
under `src/` or `tests/`, so two parallel develops would race.

Add `touches: [glob, ...]` to capability frontmatter - globs over the
project tree (typically `src/foo/**`, `tests/foo/**`). The field is
declarative: i2e-develop must not write outside the declared globs (a
post-develop check enforces this). Two capabilities whose touches globs
overlap may not run in parallel - they are serialized by the swarm-tick
scheduler.

`touches:` is optional for backward compat - capabilities without it
default to a single global touch (`**`), meaning they always serialize.

## Spec updates required
- Section 2.1: add `touches:` to frontmatter schema.
- Section 4.1: i2e-develop must respect touches.
- Section 11 (Principles): add "Declared file scope > inferred."

## Evidence of success

- id: touches-round-trips
  type: case
  provider: pytest
  query: tests/test_touches.py::test_touches_field_round_trips_through_intent_io
  expect: passes
  effort: low

- id: overlap-helper-detects-glob-intersection
  type: case
  provider: pytest
  query: tests/test_touches.py::test_paths_overlap_detects_glob_intersection
  expect: passes
  effort: medium

- id: develop-write-outside-touches-fails
  type: case
  provider: pytest
  query: tests/test_touches.py::test_develop_post_check_rejects_writes_outside_touches
  expect: passes
  effort: medium

- id: missing-touches-defaults-to-global
  type: case
  provider: pytest
  query: tests/test_touches.py::test_capability_without_touches_defaults_to_global_scope
  expect: passes
  effort: low

- id: spec-mentions-touches
  type: case
  provider: pytest
  query: tests/test_touches.py::test_spec_documents_touches_field
  expect: passes
  effort: low

## Constraints

- id: no-touches-behaves-as-today
  provider: pytest
  query: tests/test_touches.py::test_existing_capabilities_unaffected
  expect: passes
  effort: low
