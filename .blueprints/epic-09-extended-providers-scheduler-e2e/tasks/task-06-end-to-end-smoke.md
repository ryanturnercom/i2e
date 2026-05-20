# Task: End-to-end smoke test (worked example)

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** All prior epics

## Context

Spec §10 — "A user reports: a 3-space password is accepted." This task scripts that exact scenario as an executable smoke test, ensuring the whole IDEA loop works end-to-end:

1. Author a `change-password` intent with the 2 new cases + 1 constraint
2. Bump version (or create from scratch)
3. Run `i2e` — orchestrator branches to develop+evidence
4. Evidence runs pytest; the new tests fail because validator is missing
5. Adapt retries (budget allows); develop tightens validator
6. Evidence passes; current.yaml is green; shippable

This test is slow (real pytest runs in subprocess), so it lives under `tests/e2e/` and is opt-in (`pytest -m e2e`).

## Needed from User

None.

## Instructions

1. Create `tests/e2e/test_worked_example.py`:
   - Use a tmp_path project skeleton + the project's actual `i2e_core` install
   - Stage a pre-built `src/change_password.py` with the buggy validator (accepts `"   "`)
   - Stage three test files matching the spec's `tests/edge/test_short_password_rejected.py`, `tests/adversarial/test_whitespace_password_rejected.py`, `tests/constraints/test_password_min_length.py`
   - Author the intent via `i2e_core.intent_authoring.save`
   - Invoke `orchestrator.tick` repeatedly; for develop steps, run a minimal "develop simulator" function that patches `src/change_password.py` to the fixed validator on attempt 2
   - Assert:
     - First tick: develop runs (simulator returns "no change yet"), evidence runs, items fail
     - Second tick: adapt plans retries, develop simulator fixes the validator, evidence runs, all green
     - `current.yaml` shows all items pass/met
     - The bug case (`tests/adversarial/test_whitespace_password_rejected.py`) is in `current.items` and passes
2. Mark the test `@pytest.mark.e2e`
3. Add an `[tool.pytest.ini_options] markers = ["e2e: end-to-end smoke tests"]` entry to `pyproject.toml`
4. Add a `make e2e` (or `tasks.ps1 e2e`) shortcut

## Acceptance Criteria

- [x] `pytest -m e2e tests/e2e/ -q` passes
- [x] The test exercises every loop skill (i2e, develop simulator, evidence, adapt, report)
- [x] At the end, `current.yaml` shows zero failing items
- [x] At the end, `.i2e/report.html` exists and shows shippable = True
- [x] Test runtime stays under 90s on a typical dev machine

## Implementation Notes

- Created `tests/e2e/test_worked_example.py` and `tests/e2e/__init__.py`.
- Added `markers = ["e2e: ..."]` and `addopts = "-ra -m 'not e2e'"` to
  `[tool.pytest.ini_options]` so the default suite EXCLUDES the e2e marker.
  Use `pytest -m e2e` (or `./tasks.ps1 e2e`) to run it.
- Added `e2e` and `all` subcommands to `tasks.ps1`.
- Project skeleton staged under `tmp_path`:
  - `.i2e/` subdirs
  - `src/change_password.py` — buggy validator (only checks
    `len(p) > 0`, so `"   "` is accepted)
  - `tests/edge/test_short_password_rejected.py`
  - `tests/adversarial/test_whitespace_password_rejected.py`
  - `tests/constraints/test_password_min_length.py`
  - `conftest.py` adding `src/` to `sys.path` for pytest subprocesses
  - `.claude/skills/i2e-provider-pytest/` copied in so discovery finds
    the provider regardless of cwd
- Flow exercised:
  1. `intent_authoring.save` writes the capability (Intent)
  2. `orchestrator.decide` → `DevelopAndEvidence` → `tick` runs evidence
     via the REAL `i2e-provider-pytest` (subprocess). All 3 items fail.
  3. `adapt.plan` reports all 3 as retries with budget remaining (medium
     case ⇒ max 6, attempts_used 1).
  4. Develop simulator patches `src/change_password.py` to the correct
     validator.
  5. `evidence_runner.run` re-collects evidence — all 3 pass.
  6. `decide()` is now `Shippable`; `report.render` writes
     `.i2e/report.html`; `build_view_model(...).shippable is True`.
- Runtime: ~1.4 seconds on Windows (well under the 90s budget).
