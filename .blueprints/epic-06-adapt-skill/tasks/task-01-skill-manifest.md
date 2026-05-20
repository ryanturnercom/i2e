# Task: SKILL.md manifest for i2e-adapt

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-02-config-schema (epic 01)

## Context

`i2e-adapt` decides what to do when evidence shows a non-passing item. It either spends from the effort budget on another develop+evidence cycle, or escalates to a pending file.

## Needed from User

None.

## Instructions

1. Create `.claude/skills/i2e-adapt/SKILL.md`:

```markdown
---
name: i2e-adapt
description: Inspect current.yaml; for non-passing items, either spend budget on another develop+evidence cycle or escalate to a pending file. Also applies resolved pendings back to intents.
license: Apache-2.0
metadata:
  tier: loop
  version: "0.1.0"
---

# i2e-adapt

## When to use
- Orchestrator's decision tree branch 3 (trending/unmet items with budget remaining)
- Orchestrator's decision tree branch 1 (apply resolved pendings) calls `i2e_core.adapt.apply_resolutions` directly

## Inputs
- `capability` (required)

## Outputs
- Either signals "retry develop+evidence" with the next attempt counter
- Or writes `.i2e/pending/<date>-<cap>-<id>.yaml` (escalation)

## Workflow
1. Read `current.yaml`
2. For each non-passing item (verdict in fail / unmet / trending):
   a. Look up effort tier → `max_attempts`
   b. If `attempts_used < max_attempts` ⇒ propose a code/intent change rationale; signal retry
   c. Else ⇒ write escalation pending file with the 3-most-recent attempts and a 4-option `ask:`
3. Return a summary to the orchestrator

## Boundaries
- READ: everything under .i2e/
- WRITE: .i2e/pending/**, .i2e/logs/** (tick log writer)
- NEVER WRITE: src/**, .i2e/intents/** (resolution applier handles intents — but it's a separate, gated entry point)
```

2. Stub `src/i2e_core/adapt.py` with entry points: `plan(root, capability) -> AdaptPlan`, `apply_resolutions(root) -> list[Path]`, `escalate(root, capability, item_id) -> Path`

## Acceptance Criteria

- [x] SKILL.md exists with valid frontmatter
- [x] Adapt's Boundaries section makes the intent-writing carve-out explicit
- [x] `adapt.plan`, `adapt.apply_resolutions`, `adapt.escalate` are importable stubs

## Implementation Notes

- Created `.claude/skills/i2e-adapt/SKILL.md` with the spec-required
  frontmatter (`tier: loop`, `version: 0.1.0`) and an explicit
  "Intent-file carve-out" callout under **Boundaries** documenting that
  `apply_resolutions` is the single gated exception to the "only
  `i2e-intent` may write to `.i2e/intents/`" rule, and that choice 4
  (accept) writes only to `current.yaml`.
- `src/i2e_core/adapt.py` ships full implementations (not stubs) of
  `plan`, `escalate`, `has_open_escalation`, and `apply_resolutions`,
  plus models `AdaptPlan`, `ItemBudget`, `ResolutionApplied` — see
  later tasks for detail.
