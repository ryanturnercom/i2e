# Task: SKILL.md manifest for i2e-intent

**Status:** [✓] Completed
**Completed:** 2026-05-19

**Dependencies:** task-04-intent-validator (epic 01)

## Implementation Notes
- `.claude/skills/i2e-intent/SKILL.md` created with frontmatter (name, description, license, tier=loop, version=0.1.0).
- `src/i2e_core/intent_template.py` exposes `default_capability(slug, watcher) -> Capability` and `today_utc()`.
- The scaffold seeds one evidence item with `provider="pytest"`, `query="tests/test_<slug>.py"`, `expect="passes"`, `effort="medium"` so it passes `validate_capability(installed_providers={"pytest"})` out of the box.
- `today_utc()` is exposed as a function (not a constant) so tests can monkeypatch it.

## Context

`i2e-intent` is the only loop skill that writes to `.i2e/intents/`. Its SKILL.md must declare its scope and the validation gate so the orchestrator and the agent both honor it.

## Needed from User

None.

## Instructions

1. Create `.claude/skills/i2e-intent/SKILL.md`:

```markdown
---
name: i2e-intent
description: Author or edit a Capability intent file in .i2e/intents/. Validates on save against forced-evidence rules. The only skill that touches draft intents.
license: Apache-2.0
metadata:
  tier: loop
  version: "0.1.0"
---

# i2e-intent

Walks the user through authoring or editing one Capability file. Refuses to save invalid intents (missing provider, unknown provider, zero evidence items).

## When to use
- The user says "I want to add a capability called X"
- The user wants to add evidence to an existing capability
- A bug needs to become a Case (spec §10)

## Inputs
- Capability slug (kebab-case)
- Status (`draft` | `active` | `retired`)
- One or more Evidence items / Constraints

## Outputs
- `.i2e/intents/<slug>.md` (created or updated)
- Validation report (empty on success)

## Workflow
1. Resolve or prompt for the capability slug
2. Load existing intent if present (else start from a template)
3. Walk through evidence + constraint items (add/edit/remove)
4. Run `i2e_core.validator.validate_capability_with_config(...)` with installed providers
5. If invalid, show errors and refuse to save
6. If valid, bump `version` when material changes occurred, set `updated` to today, atomic-write the file
```

2. Add a helper module `src/i2e_core/intent_template.py` exposing `default_capability(slug: str, watcher: str) -> Capability` — a minimal valid scaffold with one example evidence item (provider=`pytest`, query=`tests/test_<slug>.py`)

## Acceptance Criteria

- [ ] `.claude/skills/i2e-intent/SKILL.md` exists with valid frontmatter
- [ ] `default_capability("foo", "@me")` returns a `Capability` that passes `validate_capability(installed_providers={"pytest"})`
- [ ] The template uses today's date (UTC) for `created` and `updated`
