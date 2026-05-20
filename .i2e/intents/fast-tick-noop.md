---
capability: fast-tick-noop
created: '2026-05-20'
updated: '2026-05-20'
version: 2
status: active
watcher: '@ryan'
---

# Fast no-op tick

A no-op orchestrator tick (zero active intents, no resolved pendings) must
complete well under 100ms wall-clock. Today the loop walks all five decision
branches even when there is nothing to do, and `preflight` re-parses and
re-validates every active intent on every tick — wasted work when the intent
set has not changed.

Two complementary fixes:

1. **Short-circuit in `decide()`** — at the top of
   `i2e_core.orchestrator.decide`, if there are no active capabilities AND no
   resolved pendings on disk, return `Shippable()` immediately. Skips the
   pending walk, current.yaml reads, version-bump comparisons, and target
   window math entirely.

2. **Preflight cache** — hash `{intent_path: mtime_ns}` over
   `.i2e/intents/**` and persist the last green validation result to
   `.i2e/.preflight_cache.json`. On the next tick, if the hash is unchanged,
   skip re-parsing and return the cached `PreflightResult`. Any mtime change
   (edit, add, remove) invalidates the cache and forces a fresh validation.

Both must preserve the existing `TickResult` contract: same fields, same
action ordering, same `actions_log` format. The only observable change is
latency.

## Evidence of success

- id: noop-tick-under-100ms
  type: case
  provider: pytest
  query: tests/test_fast_tick_noop.py::test_noop_tick_completes_under_100ms
  expect: passes
  effort: medium

- id: short-circuit-on-drafts
  type: case
  provider: pytest
  query: tests/test_fast_tick_noop.py::test_decide_short_circuits_when_only_drafts
  expect: passes
  effort: low

- id: cache-invalidates-on-mtime
  type: case
  provider: pytest
  query: tests/test_fast_tick_noop.py::test_preflight_cache_invalidates_on_intent_mtime_change
  expect: passes
  effort: medium

- id: invalid-intent-still-fails-after-edit
  type: case
  provider: pytest
  query: tests/test_fast_tick_noop.py::test_invalid_intent_fails_preflight_after_edit_despite_cache
  expect: passes
  effort: medium

## Constraints

- id: tick-contract-unchanged
  provider: pytest
  query: tests/test_fast_tick_noop.py::test_tick_result_contract_unchanged
  expect: passes
  effort: low
