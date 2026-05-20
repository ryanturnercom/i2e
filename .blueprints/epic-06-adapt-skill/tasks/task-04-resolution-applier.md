# Task: Resolution applier

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-03-pending-generator

## Context

A resolved escalation contains the human's chosen path from 4 options:
1. Loosen the target (e.g. modify `expect`)
2. Try a new approach (free-form text)
3. Retire this target (delete item from intent)
4. Accept current state as "met" / "pass"

The applier translates each into an intent-file edit (or, for option 4, a current.yaml edit). After applying, the pending file is archived to `logs/`.

This is the ONE place outside `i2e-intent` that may modify `.i2e/intents/*.md`. It is gated by being callable only from the orchestrator's preflight branch 1.

## Needed from User

None.

## Instructions

1. Implement `src/i2e_core/adapt.py::apply_resolutions(root) -> list[ResolutionApplied]`:
   - `ResolutionApplied(BaseModel)`: `pending_path: Path`, `capability: str`, `item_id: str`, `choice: int`, `intent_changed: bool`
   - Iterate `list_resolved_pending(root)`
   - For each, parse the resolution field — expect format `"1) <reason>"`, `"2) <new approach text>"`, `"3) <reason>"`, `"4) <reason>"`. Be forgiving: accept `1`, `1.`, `1)`, `option 1`, `loosen`, `retire`, `accept`, `new`
2. Apply per choice:
   - **1 (loosen)**: parse a `new expect: <value>` line from the resolution; update `EvidenceItem.expect`. If no new value, raise — refuse silent edits
   - **2 (new approach)**: leave intent untouched but reset `attempts_used` to 0 in `current.yaml` so the loop tries fresh; record the approach in a new tick log entry
   - **3 (retire)**: remove the item from the capability; bump `version`
   - **4 (accept)**: in `current.yaml`, set the item's verdict to `pass` (for case) or `met` (for target); leave intent untouched
3. After applying, `archive_pending(root, path)` moves the file to `logs/`
4. Return the list of applied resolutions — the orchestrator uses this for its tick log

## Acceptance Criteria

- [x] All 4 resolution choices are supported and each modifies the right artifact
- [x] Option 1 without a new value raises a clear error (no silent intent edits)
- [x] After apply, the pending file no longer exists in `.i2e/pending/` and DOES exist in `.i2e/logs/`
- [x] Option 3 (retire) bumps the intent version
- [x] Option 2 (new approach) resets `attempts_used` for the item and records the approach text
- [x] Multiple resolved pendings in one call all apply (no partial application on error — wrap in best-effort, log per-file failures, continue)

## Implementation Notes

- `apply_resolutions(root) -> list[ResolutionApplied]` returns a Pydantic
  list (not a list of paths) so the orchestrator can log per-resolution
  detail.
- Resolution parser (`_parse_choice`) accepts:
  `1`, `1.`, `1)`, `option 1`, `loosen`, `2`, `new`, `approach`, `3`,
  `retire`, `4`, `accept` (case-insensitive). Word-boundary regex prevents
  e.g. "newer" matching "new".
- Option 1 (loosen): requires a `new expect: <value>` line; raises
  `ValueError` if missing. Bumps `frontmatter.version` AND
  `frontmatter.updated = today`. Writes via `intent.write_intent` (atomic).
- Option 2 (new approach): does NOT touch the intent. Resets
  `current.items[item_id].attempts_used = 0` and stores the approach text
  under `raw.new_approach` for the next develop pass.
- Option 3 (retire): scans both `evidence` and `constraints`. Bumps
  `frontmatter.version` and `frontmatter.updated`.
- Option 4 (accept): looks up the item's type from the intent;
  case/constraint → verdict `pass`, target → verdict `met`. Intent is
  untouched.
- Errors on individual files are caught and the file is left in
  `.i2e/pending/` so the operator can inspect — best-effort batch.
- The intent-file write goes through `intent.write_intent`, which is
  atomic. SKILL.md and the function docstring both call out that
  `apply_resolutions` is the single carve-out from the "only `i2e-intent`
  writes intents" rule.
