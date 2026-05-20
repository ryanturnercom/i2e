# Task: SKILL.md manifest for i2e-evidence

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-05-evidence-writer (epic 01), task-01-provider-contract (epic 02)

## Context

`i2e-evidence` runs every provider for a capability, writes a `runs/<id>.yaml` snapshot, and rewrites `current.yaml`. It is invoked by the orchestrator after develop and by adapt after a code change.

## Needed from User

None.

## Instructions

1. Create `.claude/skills/i2e-evidence/SKILL.md`:

```markdown
---
name: i2e-evidence
description: For each evidence item and constraint in a capability, invoke its provider and record the verdict. Writes runs/<id>.yaml + current.yaml. Does not modify code.
license: Apache-2.0
metadata:
  tier: loop
  version: "0.1.0"
---

# i2e-evidence

## When to use
- After `i2e-develop` makes a change
- For periodic target re-evaluation (window elapsed)
- Standalone smoke check requested by user

## Inputs
- `capability` (required)
- `items` (optional, default = all): subset of item ids to re-evaluate

## Outputs
- `.i2e/evidence/<cap>/runs/<run-id>.yaml` (immutable snapshot)
- `.i2e/evidence/<cap>/current.yaml` (rewritten)
- Summary returned to orchestrator: `{pass: N, fail: N, met: N, unmet: N, awaiting: N}`

## Boundaries
- READ: `.i2e/intents/<cap>.md`, `.i2e/evidence/<cap>/current.yaml`, src/**
- WRITE: `.i2e/evidence/<cap>/**`, `.i2e/pending/**` (only via async providers)
- NEVER WRITE: src/**, .i2e/intents/**

## Workflow
1. Load capability + validate (forced evidence check)
2. Resolve providers for every item + constraint
3. Generate a `run_id`
4. For each item: invoke provider → translate to `ItemVerdict` (carry over `attempts_used` from prior current.yaml for non-passing verdicts)
5. Write `runs/<run-id>.yaml` (immutable; will fail if id collides)
6. Rewrite `current.yaml` atomically
7. Return summary
```

2. Stub `src/i2e_core/evidence_runner.py` with the entry point signature `def run(root: Path, capability: str, only_items: list[str] | None = None) -> RunSummary`

## Acceptance Criteria

- [x] SKILL.md exists with valid frontmatter
- [x] `evidence_runner.run` is importable (full implementation, not a stub)
- [x] SKILL.md's Boundaries section explicitly forbids writing to src/ and intents/

## Implementation Notes

- Wrote `.claude/skills/i2e-evidence/SKILL.md` with frontmatter (name,
  description, license, tier=loop, version=0.1.0), Boundaries (READ /
  WRITE / NEVER WRITE), Workflow, and Python-helpers references.
- Created `src/i2e_core/evidence_runner.py` with `run(root, capability,
  only_items=None) -> RunSummary` as a full implementation (not a stub) —
  see task-02 / task-04 notes.
- The Boundaries section explicitly forbids writing to `src/**` and
  `.i2e/intents/**`. WRITE is limited to `.i2e/evidence/<cap>/**`,
  `.i2e/pending/**` (via async providers), and `.i2e/logs/**` (only when
  archiving a resolved pending file).
- Added a Python-helpers reference list and a CLI helper section so
  users can run evidence from the shell without going through the
  orchestrator.
