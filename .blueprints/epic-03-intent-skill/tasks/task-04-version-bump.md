# Task: Version bump + updated-date logic

**Status:** [✓] Completed
**Completed:** 2026-05-19

**Dependencies:** task-02-authoring-flow

## Implementation Notes
- `intent.items_signature(cap)` lives in `intent.py` (it's a property of intent shape, not authoring policy). SHA-256 hex of `dump_yaml({"evidence": [...], "constraints": [...]})` with each list sorted by `id` and default fields dropped (`effort=medium`, `window=None`, `type=constraint`).
- `intent.diff_summary(old, new)` returns a single human-readable sentence (e.g. `Added evidence: brand-new. Bumped version 1 -> 2.`). Handles added/removed/changed evidence and constraints; explicitly notes description-only changes and "no material changes" cases.
- `save()` reads the on-disk copy when present, compares signatures, and either keeps `version` or bumps it by 1. New files keep the in-memory version (typically 1 from the scaffold).
- `updated` is always rewritten to `today_utc()` regardless of whether the version bumped.
- Reordering items (same set, different insertion order) produces the SAME signature because the canonicalization sorts each list by `id` before YAML-dumping.

## Context

The orchestrator's decision tree (spec §6.1) compares the intent's `version` against the `intent_version` recorded in `current.yaml` to decide whether to re-run develop+evidence. So version bumps must:

- Happen automatically when evidence or constraints change
- NOT happen on description-only edits (the loop ignores prose)
- Use a stable canonicalization so the same logical change produces the same hash regardless of YAML key order

## Needed from User

None.

## Instructions

1. Add to `src/i2e_core/intent.py`:
   - `def items_signature(cap: Capability) -> str` — sha256 of `dump_yaml({"evidence": [...], "constraints": [...]})` after sorting each list by `id` and dropping defaults
2. Update `intent_authoring.save`:
   - If the file does not exist on disk → version stays 1, no bump
   - If it exists and `items_signature(new) != items_signature(old)` → `version = old.version + 1`
   - Else → keep old version
3. Always set `updated` to today regardless of bump (so the file shows recency)
4. Expose `def diff_summary(old: Capability, new: Capability) -> str` returning a human-readable diff for the LLM to show before saving (e.g. "Added evidence: short-password-rejected. Bumped version 1 → 2.")

## Acceptance Criteria

- [ ] Editing only the description text does not bump version
- [ ] Adding an evidence item bumps version by 1
- [ ] Removing a constraint bumps version by 1
- [ ] Reordering items (same set, different order in YAML) does NOT bump version
- [ ] `updated` always reflects today's date on save
