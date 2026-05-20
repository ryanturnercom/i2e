# Task: SKILL.md manifest for i2e-develop

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** None (independent of other epic-04 tasks)

## Context

`i2e-develop` is the build step. It must be unambiguous about its scope: writes only to `src/` and `tests/`, reads `.i2e/intents/` + `.i2e/context/`, never writes inside `.i2e/`.

## Needed from User

None.

## Instructions

1. Create `.claude/skills/i2e-develop/SKILL.md`:

```markdown
---
name: i2e-develop
description: Build the System in src/ from the current active intents. Reads .i2e/context/ for standing reference; writes only to src/ and tests/. Never touches .i2e/.
license: Apache-2.0
metadata:
  tier: loop
  version: "0.1.0"
---

# i2e-develop

## When to use
- Called by `i2e` orchestrator when an active intent has a higher `version` than the last `intent_version` recorded in `current.yaml`
- Called by `i2e-adapt` to retry after an evidence failure within budget

## Boundaries
- READ: `.i2e/intents/<cap>.md`, `.i2e/context/*`, `src/**`, `tests/**`, `.i2e/evidence/<cap>/current.yaml` (to see prior failure)
- WRITE: `src/**`, `tests/**` only
- NEVER WRITE: anything under `.i2e/`

## Workflow
1. Resolve target capability (passed in by orchestrator)
2. Run `i2e_core.develop.diff_against_current(cap)` to learn what's new since `intent_version`
3. Load standing context from `.i2e/context/*`
4. Write/update code in `src/` and tests in `tests/` to satisfy every Case + Constraint
5. Do NOT run pytest — that's `i2e-evidence`'s job
6. Return a summary the orchestrator logs into the tick

## Forbidden
- Mocking the provider — let evidence actually run
- Editing the intent file — that's `i2e-intent`'s job
- Skipping constraints — they gate ship just like cases
```

2. Stub `src/i2e_core/develop.py` with `def diff_against_current(root: Path, capability: str) -> dict` — returns `{"new_items": [...], "changed_items": [...], "removed_items": [...], "prior_version": int | None}` (full impl in task-03)

## Acceptance Criteria

- [✓] SKILL.md exists with valid frontmatter
- [✓] `develop.diff_against_current` is importable (returns empty dict if no prior evidence)
- [✓] SKILL.md's "Forbidden" section explicitly lists not-mocking, not-editing-intent, not-skipping-constraints

## Implementation Notes

- Created `.claude/skills/i2e-develop/SKILL.md` with frontmatter `tier: loop`,
  `version: 0.1.0`, and explicit READ/WRITE/NEVER-WRITE boundaries.
- Workflow section references the deterministic helpers in `i2e_core.develop`
  and `i2e_core.context` so the LLM knows the exact call sequence.
- "Forbidden" section now lists five rules (not-mocking, not-editing-intent,
  not-skipping-constraints, not-writing-inside-.i2e/, not-running-providers).
- Implemented `src/i2e_core/develop.py` in this task as a real implementation
  (not a stub) so the full epic could share one file; the later tasks fleshed
  out the helpers it points at.
