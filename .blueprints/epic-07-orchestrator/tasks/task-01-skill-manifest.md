# Task: SKILL.md manifest for i2e

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** None (declarative only)

## Context

`i2e` is the front-door skill. Humans and schedulers invoke it; it runs one step. Its SKILL.md must be tight — the decision tree is the contract.

## Needed from User

None.

## Instructions

1. Create `.claude/skills/i2e/SKILL.md`:

```markdown
---
name: i2e
description: Orchestrator. Runs a preflight scan and advances the project by exactly one step using the IDEA loop decision tree. Auto-invokes i2e-report after any state-changing tick.
license: Apache-2.0
metadata:
  tier: loop
  version: "0.1.0"
---

# i2e

## When to use
- A human says "run i2e" / "tick the loop"
- A scheduler fires (`/schedule` routine, OS scheduler)

## Workflow
1. **Preflight** (`i2e_core.orchestrator.preflight(root)`):
   - Re-run forced-evidence validation across all active intents
   - Halt the tick with a clear error if any intent is invalid (`i2e-intent` is the fix)
2. **Decide** (`i2e_core.orchestrator.decide(root)`):
   - Returns the first matching action from the 5-branch tree:
     1. Resolved pending → `i2e_core.adapt.apply_resolutions`
     2. Stale develop (intent version > current's recorded version) → `i2e-develop` then `i2e-evidence`
     3. Trending/unmet items with budget → `i2e-adapt` → `i2e-develop` + `i2e-evidence`
     4. Target window elapsed → `i2e-evidence` (single item)
     5. All green → mark shippable; no-op
3. **Execute** the action; collect a list of action strings
4. **Tick log**: if any actions occurred, `tick_log.write_tick`
5. **Report**: ALWAYS call `i2e_core.report.render(root)` if anything changed

## Boundaries
- READ: all of `.i2e/`, `src/`, `tests/`
- WRITE: `.i2e/logs/**`, `.i2e/report.html`, plus whatever the dispatched skill writes
- NEVER WRITE DIRECTLY: `.i2e/intents/**`, `.i2e/evidence/**`, `src/**`, `tests/**` (always via a downstream skill)

## Exit codes (CLI invocation)
- 0: tick completed (regardless of green/yellow/red — that's reflected in current.yaml)
- 1: preflight failed
- 2: an executing skill raised
```

2. Stub `src/i2e_core/orchestrator.py` with: `preflight(root)`, `decide(root) -> Action`, `tick(root) -> TickResult`

## Acceptance Criteria

- [x] SKILL.md exists with valid frontmatter
- [x] SKILL.md's decision tree mirrors spec §6.1 exactly (5 branches, order preserved)
- [x] Stub functions are importable

## Implementation Notes

- Created `.claude/skills/i2e/SKILL.md` with the spec-required frontmatter
  (`tier: loop`, `version: 0.1.0`) and the 5-branch decision tree mirrored
  exactly in the Workflow section.
- `src/i2e_core/orchestrator.py` ships full implementations (not stubs) of
  `preflight`, `decide`, and `tick` plus the Pydantic v2 models
  `PreflightResult`, `TickResult`, the action discriminated union
  (`ApplyResolutions`, `DevelopAndEvidence`, `AdaptThenRetry`,
  `ReEvaluateItem`, `Shippable`), and `parse_window`.
- Created a minimal stub at `src/i2e_core/report/__init__.py` exposing
  `render(root) -> Path | None` returning `None`. Epic 08 will replace the
  body. The accompanying `src/i2e_core/report/templates/.gitkeep` reserves
  the templates directory.
