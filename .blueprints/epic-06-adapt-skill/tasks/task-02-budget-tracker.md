# Task: Budget tracker

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-01-skill-manifest

## Context

Maps each non-passing item to either "retry" or "escalate" based on the effort tier and `attempts_used` in `current.yaml`.

## Needed from User

None.

## Instructions

1. Implement `src/i2e_core/adapt.py::plan(root, capability) -> AdaptPlan`:
   - `AdaptPlan(BaseModel)`: `capability: str`, `retries: list[ItemBudget]`, `escalations: list[ItemBudget]`, `done: list[str]`
   - `ItemBudget(BaseModel)`: `item_id: str`, `effort: str`, `attempts_used: int`, `max_attempts: int`, `verdict: str`
2. Logic:
   - Read `current.yaml` and intent
   - For each item in current.items where verdict in `{"fail","unmet","trending"}`:
     - Determine `item_type` (case/target/constraint) from the intent
     - `max_attempts = resolve_max_attempts(cfg, item_type, item.effort)`
     - If `attempts_used < max_attempts` → append to `retries`
     - Else → append to `escalations`
   - Items in `{"pass","met","awaiting_human"}` → `done` list
3. `lazy` tier ⇒ `max_attempts == 0` ⇒ first failure goes straight to escalation
4. Tests: each tier (lazy/low/medium/high) on case vs. target; one transition point per tier

## Acceptance Criteria

- [x] `plan` returns empty `retries` and `escalations` when all items pass
- [x] `lazy` items escalate on first failure (attempts_used=1, max=0)
- [x] `medium` case item with attempts_used=5, max=6 ⇒ retry
- [x] `medium` case item with attempts_used=6 ⇒ escalate
- [x] `awaiting_human` items never appear in retries or escalations (they're in `done`)

## Implementation Notes

- `plan(root, capability)` lives in `src/i2e_core/adapt.py`.
- Pydantic v2 models `AdaptPlan` and `ItemBudget` use `extra="forbid"` for
  schema-tightness.
- Constraints reuse the **case** tier map (per
  `resolve_max_attempts`); the high-effort constraint test asserts
  max_attempts=10.
- Items present in `current.yaml` but missing from the intent
  (e.g. recently retired) land in `done`; reconciliation will scrub them on
  the next evidence pass.
- Items with an open pending file (any kind) are placed in `done` so adapt
  is idempotent across ticks — the orchestrator can re-run `plan` after a
  failed develop pass without generating a duplicate escalation.
