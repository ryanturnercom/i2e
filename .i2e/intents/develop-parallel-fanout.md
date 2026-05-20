---
capability: develop-parallel-fanout
created: '2026-05-20'
updated: '2026-05-20'
version: 1
status: active
watcher: '@ryan'
depends_on:
  - intent-touches-field
touches:
  - 'src/i2e_core/develop.py'
  - 'tests/test_develop_fanout.py'
  - '.claude/skills/i2e-develop/**'
  - '.documentation/I2E_simplified.md'
---

# i2e-develop fans out sub-agents per independent file

Within a single capability, `i2e-develop` runs as one linear pass today.
For capabilities that touch multiple independent files (one `src/*.py` +
its sibling `tests/test_*.py` + a fixture), there is no reason to write
them serially.

Rewrite `i2e-develop`:
1. Read the intent + `touches:` globs.
2. Plan a file-level task list: each file gets a goal description.
3. Group goals into a dependency-free batch (two goals on the same file ->
   sequential; goals on distinct files -> parallel).
4. Spawn one Agent per parallel slot (the Agent tool already supports
   parallel multi-tool-call); each writes its own file.
5. Aggregate results, run evidence.

Requires `intent-touches-field` to know what files are in scope.

## Spec updates required
- Section 4.1: describe i2e-develop's fan-out planning behavior.
- Section 11: add principle "Parallelize within capability when files are
  independent."

## Evidence of success

- id: develop-plans-parallel-batch-on-independent-files
  type: case
  provider: pytest
  query: tests/test_develop_fanout.py::test_planner_groups_independent_files_into_parallel_batch
  expect: passes
  effort: high

- id: develop-serializes-shared-files
  type: case
  provider: pytest
  query: tests/test_develop_fanout.py::test_planner_serializes_goals_on_same_file
  expect: passes
  effort: medium

- id: develop-aggregates-outputs
  type: case
  provider: pytest
  query: tests/test_develop_fanout.py::test_parallel_writes_merge_into_consistent_src_state
  expect: passes
  effort: medium

- id: develop-respects-touches-globs
  type: case
  provider: pytest
  query: tests/test_develop_fanout.py::test_planner_never_emits_goal_outside_touches
  expect: passes
  effort: medium

- id: spec-mentions-develop-fanout
  type: case
  provider: pytest
  query: tests/test_develop_fanout.py::test_spec_documents_develop_fanout
  expect: passes
  effort: low

## Constraints

- id: single-file-capability-still-serial
  provider: pytest
  query: tests/test_develop_fanout.py::test_capability_with_one_file_runs_without_fanout_overhead
  expect: passes
  effort: low
