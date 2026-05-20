# Epic: i2e-intent Skill

**Status:** [✓] Completed
**Source spec:** .documentation/I2E_simplified.md
**Started:** 2026-05-19
**Completed:** 2026-05-19

## Context

`i2e-intent` is the only skill that touches `draft` intents. It lets a human author or edit a Capability file with the agent's help, then validates on save against forced-evidence rules.

A Capability file lives at `.i2e/intents/<capability>.md` and has frontmatter (capability, version, status, watcher, dates) plus three Markdown sections: free-form description, Evidence of success, Constraints.

## Implementation Overview

- Ship a SKILL.md at `~/.claude/skills/i2e-intent/SKILL.md` (or repo `.claude/skills/i2e-intent/` for project-local install)
- An interactive authoring/edit flow that:
  - Prompts for capability slug, status, watcher (or reads from existing file)
  - Walks through evidence items (id, type, provider, query, expect, effort) — one at a time
  - Walks through constraints
- A save gate that calls `i2e_core.validator.validate(capability)` and refuses to save invalid intents — the human must resolve before the file is written
- Version bump logic: if an active intent's evidence/constraints changed materially, increment `version` and update `updated`

## Tasks

- [✓] [task-01: SKILL.md manifest for i2e-intent](tasks/task-01-skill-manifest.md)
- [✓] [task-02: Interactive authoring/edit flow](tasks/task-02-authoring-flow.md)
- [✓] [task-03: Save-time validation gate](tasks/task-03-save-validation.md)
- [✓] [task-04: Version bump + updated-date logic](tasks/task-04-version-bump.md)
- [✓] [task-05: Tests for the intent skill flows](tasks/task-05-tests.md)

## Outcome

The `i2e-intent` skill is fully implemented and green.

- **Skill manifest:** `.claude/skills/i2e-intent/SKILL.md` with frontmatter, when-to-use, inputs/outputs, workflow, and recipes for common operations (add capability, add evidence, retire item, draft→active, dry-run save).
- **Deterministic Python core:** `intent_template.default_capability`, `intent_authoring.{load_or_init, upsert_evidence, upsert_constraint, remove_item, save}`, `intent_save_gate.gate`, plus `intent.items_signature` and `intent.diff_summary`.
- **Forced-evidence enforcement:** every save runs `validate_capability_with_config` against the installed-provider set. Errors are prefixed with `<slug> > <item id>` and "provider not installed" errors include the scanned skills dirs.
- **Version-bump semantics:** SHA-256 of YAML-dumped, id-sorted, defaults-dropped evidence + constraints. Reordering and re-stating defaults are no-ops; adding, removing, or changing an item bumps by 1. Description-only edits never bump. `updated` always rewrites to today.
- **Atomic writes:** save() refuses to write on validation failure and uses the existing `write_intent` (which goes through `atomic_write`).
- **Tests:** 31 new tests under `tests/intent/` (test_authoring + test_save_gate + test_version_bump), with a hermetic `fake_skills_root` fixture that stubs `installed_provider_names`. All 115 tests in the suite pass.

### Final metrics
- Test result: 115 passed (84 prior + 31 new)
- Coverage on `src/i2e_core/`: **96%** total
  - `intent.py`: 94%
  - `intent_authoring.py`: 100%
  - `intent_save_gate.py`: 94%
  - `intent_template.py`: 100%

### Files created
- `.claude/skills/i2e-intent/SKILL.md`
- `src/i2e_core/intent_template.py`
- `src/i2e_core/intent_authoring.py`
- `src/i2e_core/intent_save_gate.py`
- `tests/intent/__init__.py`
- `tests/intent/conftest.py`
- `tests/intent/test_authoring.py`
- `tests/intent/test_save_gate.py`
- `tests/intent/test_version_bump.py`

### Files modified
- `src/i2e_core/intent.py` — added `items_signature` and `diff_summary` (and an `import hashlib` + `dump_yaml`).
