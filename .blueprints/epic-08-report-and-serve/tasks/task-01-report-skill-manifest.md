# Task: SKILL.md manifest for i2e-report

**Status:** [ ] Pending

**Dependencies:** None

## Context

`i2e-report` is deterministic Python — zero LLM tokens. The SKILL.md exists for discovery; the implementation is pure code.

## Needed from User

None.

## Instructions

1. Create `.claude/skills/i2e-report/SKILL.md`:

```markdown
---
name: i2e-report
description: Render .i2e/report.html from current state. Deterministic Python — zero LLM tokens. Auto-invoked by the orchestrator after any state-changing tick.
license: Apache-2.0
metadata:
  tier: loop
  version: "0.1.0"
  deterministic: true
---

# i2e-report

This skill is a thin wrapper around `i2e_core.report.render(root)`. Invoke it directly; no LLM reasoning is required or wanted.

## Outputs
- `.i2e/report.html` (rewritten)

## Deep-link fragments
- `#cap/<capability>` → capability card
- `#item/<capability>/<id>` → specific evidence item
- `#pending/<filename>` → pending file
- `#tick/<tick-id>` → tick log entry

## When NOT to use
- Do not invoke during preflight failures — the dashboard would be misleading
- Do not invoke for empty ticks — the orchestrator already gates this
```

2. Stub `src/i2e_core/report/__init__.py` with `def render(root: Path) -> Path` — full impl in tasks 02–04

## Acceptance Criteria

- [ ] SKILL.md exists with `metadata.deterministic: true`
- [ ] `i2e_core.report.render` is importable
