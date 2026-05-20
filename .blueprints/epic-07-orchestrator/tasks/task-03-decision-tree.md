# Task: Decision tree evaluator

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-02-preflight-scan, plus dependencies on all loop skills (epics 03–06)

## Context

The 5-branch decision tree (spec §6.1) — evaluated in order, first match wins. Returns an `Action` describing what to do.

## Needed from User

None.

## Instructions

1. Implement `src/i2e_core/orchestrator.py::decide(root) -> Action`:
   - `Action` is a tagged union:
     - `ApplyResolutions()`
     - `DevelopAndEvidence(capability: str)`
     - `AdaptThenRetry(capability: str)`
     - `ReEvaluateItem(capability: str, item_id: str)`
     - `Shippable()` — the no-op terminal state
2. Evaluation order:
   1. `list_resolved_pending(root)` non-empty → `ApplyResolutions()`
   2. `scoped_capabilities(root)` non-empty → `DevelopAndEvidence(<first>)` (deterministic order: alphabetical by slug)
   3. For each active capability, if `adapt.plan(root, cap).retries` non-empty → `AdaptThenRetry(<first such cap>)`
   4. For each active capability, scan current.yaml for items where `verdict in {met, unmet, trending}` AND `now - last_observed > item.window` → `ReEvaluateItem`
   5. Else → `Shippable()`
3. Window parsing: implement `def parse_window(s: str) -> timedelta` supporting `Nm`, `Nh`, `Nd`, `Nw`; raise `ValueError` on unknown formats

## Acceptance Criteria

- [x] All 5 branches reachable; each returns the right `Action` variant
- [x] Order matches spec §6.1 (first match wins — resolved pending always beats stale develop)
- [x] `parse_window("5m") == timedelta(minutes=5)`, `parse_window("7d") == timedelta(days=7)`
- [x] When everything is green, returns `Shippable()`
- [x] Determinism: same state ⇒ same action across runs (alphabetical capability ordering)

## Implementation Notes

- The `Action` tagged union is modeled as five Pydantic v2 models each
  with a `Literal[...]` `kind` discriminator string
  (`apply_resolutions`, `develop`, `adapt_retry`, `reevaluate`,
  `shippable`). `Action = Union[...]` gives clean `isinstance` dispatch
  in `tick`.
- `decide` evaluation order (strict, first match wins):
  1. `list_resolved_pending` non-empty → `ApplyResolutions`.
  2. `scoped_capabilities` non-empty → `DevelopAndEvidence(<alphabetical first>)`.
  3. For each active capability (alphabetical), `adapt.plan(...).retries`
     non-empty → `AdaptThenRetry`.
  4. For each active capability (alphabetical), scan `current.items` for
     `met|unmet|trending` items where `now - last_observed > window` →
     `ReEvaluateItem`. Items without `window` or `last_observed` skipped.
  5. Otherwise → `Shippable`.
- `parse_window` regex: `^\s*(\d+)\s*([mhdw])\s*$`. `m|h|d|w` map to
  `minutes|hours|days|weeks`. Bare numbers, seconds, and other suffixes
  raise `ValueError`.
- Naive `last_observed` datetimes are coerced to UTC before the
  delta-comparison, so older fixtures without tzinfo still work.
