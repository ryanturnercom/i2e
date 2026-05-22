---
capability: tick-log-sub-actions
created: '2026-05-20'
updated: '2026-05-21'
version: 1
status: shipped
watcher: '@me'
depends_on:
- worktree-dispatch-and-merge
touches:
- src/i2e_core/tick_log.py
- tests/test_tick_log_sub_actions.py
spec: swarm-tick
spec_section: '5'
---

The tick log shape gains `sub_actions: [...]` so a batch tick records
one entry per batch member rather than collapsing into one opaque
string. The legacy `actions: [...]` field stays present and populated
(typically with the batch-level summary line) so existing tick log
readers keep working. The report renderer reads `sub_actions` when
available and falls back to `actions` otherwise.

## Evidence of success

- id: tick-log-sub-actions-implemented
  type: case
  provider: pytest
  query: tests/test_tick_log_sub_actions.py::test_implemented
  expect: passes
  effort: medium

## Constraints
