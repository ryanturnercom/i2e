# Task: Async verdict handling (awaiting_human)

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-02-provider-invocation, task-04-provider-human (epic 02)

## Context

When a provider returns `AsyncResult`, the runner must:

- Record `verdict="awaiting_human"` and `pending=<filename>` in the item's `ItemVerdict`
- NOT increment `attempts_used` (the human hasn't answered yet)
- NOT block the rest of the run

When that item is re-evaluated and the prior pending was already written, the human provider raises `FileExistsError`. The runner must catch that, look at the existing pending file:
- If `status: open` → keep the item's `awaiting_human` verdict (no new pending file)
- If `status: resolved` → translate the resolution to a real verdict, archive the pending file via `archive_pending`

## Needed from User

None.

## Instructions

1. Update `evidence_runner.run` to catch `FileExistsError` from async providers:
   - Read the existing pending file
   - If open: re-emit `awaiting_human` with the same pending basename
   - If resolved: parse `resolution` field, map `verdict_options` to a Case verdict (`yes` → pass, `no` → fail, `partial` → fail), call `archive_pending`, emit the resolved verdict
2. Add `src/i2e_core/pending.py::resolve_to_verdict(pf: PendingFile) -> ItemVerdict`:
   - For `kind="human_evaluation"`: maps `resolution` choice → pass/fail
   - For `kind="escalation"`: handled by adapt (epic 06), not evidence
3. Document in the SKILL.md (task-01) that the evidence runner is safe to re-invoke — it picks up resolutions automatically

## Acceptance Criteria

- [x] First evidence run on a `provider: human` item writes a pending file and records `awaiting_human`
- [x] Re-running evidence while the pending is `open` does NOT write a second file (FileExistsError handled silently, verdict unchanged)
- [x] Resolving the pending (`status: resolved`, `resolution: "yes"`) and re-running evidence: pending file is archived to `.i2e/logs/`, item verdict becomes `pass`
- [x] `attempts_used` is NOT incremented for `awaiting_human` verdicts

## Implementation Notes

- Added `resolve_to_verdict(pf: PendingFile) -> ItemVerdict` to
  `src/i2e_core/pending.py`. For `kind="human_evaluation"`:
  - `resolution == "yes"` → `ItemVerdict(verdict="pass", last_observed=now)`
  - `resolution in {"no", "partial"}` → `ItemVerdict(verdict="fail",
    last_observed=now, raw={"resolution": pf.resolution})`
  - Raises `ValueError` on a non-resolved file, escalation kind, or
    unknown resolution.
- Other resolutions (numeric scores from surveys) are out of scope for
  epic 05 — survey extension lands in epic 09. The docstring on
  `resolve_to_verdict` calls this out so future readers know where to
  plug the numeric branch in.
- `evidence_runner.run` catches `FileExistsError` from any provider
  (only the async ones realistically raise it). It then calls
  `_handle_file_exists(root, item, prev_attempts)` which globs
  `.i2e/pending/` for a file ending in `-<item.id>.yaml`:
  - If open → `ItemVerdict(verdict="awaiting_human",
    attempts_used=prev_attempts, pending=<basename>)` (no bump).
  - If resolved → call `resolve_to_verdict(pf)`, then `archive_pending`.
    A `pass` resolution preserves `attempts_used`; a `fail` resolution
    bumps it (`prev + 1`). This matches the rule used elsewhere in the
    runner: a fail is an attempt; a pass / awaiting is not.
- Defensive fallbacks (pending/ dir missing, no matching pending file)
  emit a `fail` with `raw.error` rather than crashing the run.
- SKILL.md (task-01) calls out that the evidence runner is safe to
  re-invoke and that resolutions are picked up automatically on the
  next run.
