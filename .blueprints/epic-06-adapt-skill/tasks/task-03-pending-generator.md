# Task: Escalation pending-file generator

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-02-budget-tracker, task-04-provider-human (epic 02)

## Context

When budget is exhausted, write a pending file with `kind: escalation` capturing the last 3 attempts and a 4-option `ask:` block (spec §6.2 example).

## Needed from User

None.

## Instructions

1. Implement `src/i2e_core/adapt.py::escalate(root, capability, item_id) -> Path`:
   - Load intent, current.yaml, and last 3 runs (`list_runs` + `read_run`)
   - Build a `PendingFile` with:
     - `kind="escalation"`
     - `escalated_at=now_utc()`
     - `reason=f"max_attempts exhausted ({attempts_used}/{max_attempts}) without meeting threshold"`
     - `expect=<from intent>`, `observed=<from current verdict>`
     - `attempts=[{run_id, changed, observed} for last 3 runs]` — `changed` comes from tick logs (epic 06 task-05); if unavailable, set to `"(no tick log)"`
     - `ask=<4-option string from spec §6.2>`
   - Call `write_pending` — atomic, refuses to overwrite an existing open pending for the same item
   - Return the path
2. Helper: `def has_open_escalation(root, capability, item_id) -> bool` — used by `adapt.plan` to avoid generating duplicate pending files when running multiple times
3. The runner-facing summary returned by `plan` excludes items that already have an open escalation

## Acceptance Criteria

- [x] `escalate` writes a file matching `pending_filename(cap, item_id)` with `kind="escalation"`
- [x] The file contains the last 3 attempts (or fewer if history is shorter)
- [x] Calling `escalate` twice for the same item: second call raises `FileExistsError`
- [x] `has_open_escalation` returns `True` for an item with an open pending of any kind
- [x] `plan` does not include items with open escalations in its `escalations` list (idempotent across ticks)

## Implementation Notes

- `escalate(root, capability, item_id)` reads the intent + `current.yaml` +
  the last 3 run snapshots, then writes a `kind: escalation` pending file
  with the spec §6.2 4-option `ask:` block.
- The `attempts` block pulls `changed` descriptions from
  `tick_log.changes_since`. When no tick log mentions the cap+item for a
  given run, the entry falls back to the literal string `"(no tick log)"`.
- If no run snapshots exist at all (very-first-tick edge case), the
  attempts block emits a single placeholder row keyed off
  `current.last_run`, so the human always sees something useful.
- `has_open_escalation(root, capability, item_id)` returns `True` for ANY
  open pending kind (not just escalations) — we don't want adapt to
  double-queue an item that's already waiting on a human evaluation.
