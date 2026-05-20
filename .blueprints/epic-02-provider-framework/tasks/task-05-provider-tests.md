# Task: Provider invocation tests

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-03-provider-pytest, task-04-provider-human

## Context

End-to-end tests that exercise the discovery → load → invoke path for both reference providers. These tests are the safety net that catches regressions when later epics (especially 05) wire providers into the evidence runner.

## Needed from User

None.

## Instructions

1. Create `tests/providers/conftest.py` with:
   - `fake_skills_root` fixture: builds a `tmp_path/.claude/skills/` tree with copies of the two provider skills
   - `provider_ctx` fixture: returns a `ProviderContext` pointed at a `tmp_path` project root
2. Create `tests/providers/test_pytest_provider.py`:
   - Discovery picks up `pytest`
   - Loading returns a callable provider
   - Invoking against a passing nodeid yields `verdict="pass"`
   - Invoking against a failing nodeid yields `verdict="fail"` with non-empty `output`
3. Create `tests/providers/test_human_provider.py`:
   - Discovery picks up `human`
   - First invocation writes a pending file and returns the basename
   - Second invocation (same item) raises `FileExistsError`
   - `archive_pending` moves the file to `logs/`
4. Create `tests/providers/test_discovery_priority.py`:
   - Project-local provider overrides user-level provider when both define `i2e-provider-fake`

## Acceptance Criteria

- [x] All provider tests pass via `pytest tests/providers/ -q`
- [x] Each test isolates filesystem state via `tmp_path`
- [x] Test runtime stays under 30s on a typical dev machine (pytest spawning is the slow part — keep test bodies small)
- [x] Coverage of `src/i2e_core/provider/` is >85%

## Implementation Notes

- 37 provider tests across `test_contract.py`, `test_pytest_provider.py`, `test_human_provider.py`, `test_discovery_priority.py`.
- `tests/providers/conftest.py` ships `fake_skills_root` (copies real skills into `tmp_path/.claude/skills/`) and `provider_ctx` (a `ProviderContext` with default config + scaffolded `.i2e/` subdirs). An autouse `_reset_provider_cache` keeps the discovery cache hermetic between tests.
- Fixture pytest modules live in `tests/providers/_fixtures/` and are masked from collection via a local `conftest.py` declaring `collect_ignore_glob`.
- Coverage: `src/i2e_core/provider/` is at 96% combined (contract 100%, discovery 93%). Whole-package coverage holds at 97%.
