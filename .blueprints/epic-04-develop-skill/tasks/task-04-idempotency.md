# Task: Idempotency via intent_version

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-03-develop-workflow

## Context

If `i2e` is invoked twice in a row with no intent changes, develop must NOT re-run. The orchestrator uses `current.yaml`'s `intent_version` field; this task ensures develop honors and updates it correctly.

The contract: develop's only "signal" of completion is the next evidence run writing `intent_version = cap.frontmatter.version` into `current.yaml`. Develop itself never writes to `.i2e/`. So idempotency lives in `diff_against_current` returning empty new/changed/removed lists.

## Needed from User

None.

## Instructions

1. Add `src/i2e_core/develop.py::needs_develop(root, capability) -> bool`:
   - Returns `True` if there is no `current.yaml` OR `current.intent_version < cap.frontmatter.version`
   - Returns `False` otherwise (no work needed)
2. Add `src/i2e_core/develop.py::scoped_capabilities(root) -> list[Capability]`:
   - Returns all active capabilities where `needs_develop` is true
3. The orchestrator (epic 07) will call `scoped_capabilities` in its decision tree
4. Tests:
   - With no prior evidence ⇒ `needs_develop == True`
   - With matching version ⇒ `False`
   - With older version ⇒ `True`

## Acceptance Criteria

- [✓] `needs_develop` returns `True` when no `current.yaml` exists
- [✓] `needs_develop` returns `False` when versions match
- [✓] `needs_develop` returns `True` when intent version > current's recorded version
- [✓] `scoped_capabilities` skips retired/draft intents (only `active`)

## Implementation Notes

- `needs_develop(root, cap_name)` parses the intent file, reads `current.yaml`,
  and returns `True` when no current exists or when
  `current.intent_version < cap.frontmatter.version`. False otherwise.
- `scoped_capabilities(root)` globs `.i2e/intents/*.md`, filters to
  `status == "active"`, and returns the capabilities for which `needs_develop`
  is True. Returns an empty list (no error) when the intents directory is
  missing. Sorted by file path for deterministic ordering.
