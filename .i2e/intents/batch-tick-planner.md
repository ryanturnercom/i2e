---
capability: batch-tick-planner
created: '2026-05-20'
updated: '2026-05-20'
version: 1
status: active
watcher: '@me'
depends_on:
- runtime-frontmatter-mirror
touches:
- src/i2e_core/swarm.py
- tests/test_batch_tick_planner.py
spec: swarm-tick
spec_section: '3'
---

Replace one-action-per-tick with one batch of non-conflicting actions
per tick. Pure planning, no I/O. Algorithm: compute the eligible set
via the existing 5-branch tree; topo-sort by `depends_on:` and drop any
capability whose parents are not yet shippable; greedy-select a batch
where no two members' `touches:` globs overlap. Output is an ordered
list of slugs the dispatcher will claim and run in parallel. A
single-active-capability project produces a one-element batch — no
batch-mode overhead, identical to today's behaviour. A `Shippable`
project still produces an empty batch (no-op tick).

## Evidence of success

- id: batch-tick-planner-implemented
  type: case
  provider: pytest
  query: tests/test_batch_tick_planner.py::test_implemented
  expect: passes
  effort: medium

## Constraints
