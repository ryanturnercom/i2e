# Task: Tests for the intent skill flows

**Status:** [✓] Completed
**Completed:** 2026-05-19

**Dependencies:** task-02-authoring-flow, task-03-save-validation, task-04-version-bump

## Implementation Notes
- `tests/intent/__init__.py`, `tests/intent/conftest.py`, and three test modules created.
- `conftest.fake_skills_root` monkeypatches `intent_save_gate.installed_provider_names` to return `{"pytest"}` regardless of arguments — this is more hermetic than the file-tree-copying approach in `tests/providers/conftest.py` because it works even when `~/.claude/skills` is unpredictable.
- `conftest.project_root` shadows the outer `tests/conftest.py::project_root` but only builds an empty `.i2e/` skeleton (no fixtures copied), which is what the intent tests need.
- 31 new tests covering: load_or_init scaffold/existing paths, upsert/remove behaviours, save-gate happy + every failure mode (unknown provider, unknown effort, zero items), dry-run no-write, dry-run still validates, signature reorder-stability + default-restatement no-op, version-bump on add/remove, no-bump on description/reorder, `updated` always today, and `diff_summary` output shapes.

## Coverage achieved
- `src/i2e_core/intent.py`: 94%
- `src/i2e_core/intent_authoring.py`: 100%
- `src/i2e_core/intent_save_gate.py`: 94%
- `src/i2e_core/intent_template.py`: 100%
- Overall `src/i2e_core/`: 96%

## Context

Test the deterministic parts of `i2e-intent`. The interactive LLM walk is out of scope; what's tested is every Python helper.

## Needed from User

None.

## Instructions

1. Add `tests/intent/test_authoring.py`:
   - `load_or_init` returns scaffold for missing slug, parsed file for existing
   - `upsert_evidence` replaces by id
   - `remove_item` is idempotent (no-op on missing id)
2. Add `tests/intent/test_save_gate.py`:
   - Save with unknown provider fails
   - Save with valid setup succeeds, file appears on disk
   - Dry-run returns path, does not write
3. Add `tests/intent/test_version_bump.py`:
   - Description-only edit: no bump
   - Add item: bump
   - Remove item: bump
   - Reorder items: no bump
4. Use a `fake_skills_root` fixture that registers `pytest` as installed so the gate accepts intents

## Acceptance Criteria

- [ ] All intent tests pass via `pytest tests/intent/ -q`
- [ ] Tests cover both the success and failure paths of the save gate
- [ ] Coverage of `i2e_core.intent`, `intent_authoring`, `intent_save_gate` is >85%
