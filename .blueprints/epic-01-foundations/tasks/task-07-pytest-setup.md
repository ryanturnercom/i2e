# Task: pytest setup + foundation tests

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-02-config-schema, task-03-intent-parser, task-04-intent-validator, task-05-evidence-writer, task-06-shared-utils

## Context

This task closes out epic 01 by adding a baseline test suite. Each foundation module needs at least one happy-path and one error-path test. These tests act as a regression net for every later epic.

## Needed from User

None.

## Instructions

1. Create `tests/fixtures/shorten-url.md` — verbatim copy of the spec's §2.1 example
2. Create `tests/conftest.py` with a `project_root` fixture that builds a temporary `.i2e/` skeleton with the fixture intent file
3. Write test modules:
   - `tests/test_paths.py` — `find_root` walks up, raises on missing
   - `tests/test_runid.py` — format + uniqueness
   - `tests/test_io_utils.py` — atomic write, YAML key order
   - `tests/test_config.py` — defaults, partial merge, `resolve_max_attempts`
   - `tests/test_intent_parser.py` — parses the fixture, serializes round-trip, rejects bad ids
   - `tests/test_validator.py` — empty capability fails rule 3; unknown provider fails rule 2; unknown effort fails config validation
   - `tests/test_evidence.py` — write + read current.yaml round-trip; refuses overwrite of run snapshot
4. Add a `Makefile` (or `tasks.ps1` for Windows-first; pick one and document in README) with `test` target running `pytest -q`

## Acceptance Criteria

- [✓] `pytest -q` passes with at least 15 tests across the 7 modules (47 tests total)
- [✓] Tests use `tmp_path` rather than touching real `.i2e/` directories
- [✓] At least one test exercises each acceptance criterion from tasks 02–06
- [✓] Coverage of `src/i2e_core/` is >85% (`pytest --cov=i2e_core --cov-report=term-missing`) — achieved 97%

## Implementation Notes

- `tests/conftest.py` exposes `fixtures_dir`, `shorten_url_fixture`, and `project_root` (a `tmp_path`-backed `.i2e/` skeleton with the spec's shorten-url fixture copied in).
- `tests/fixtures/shorten-url.md` is a verbatim copy of the spec §2.1 example.
- Test modules: `test_paths.py`, `test_runid.py`, `test_io_utils.py`, `test_config.py`, `test_intent_parser.py`, `test_validator.py`, `test_evidence.py` — 47 tests total.
- Final coverage: 97% (target was >85%). Modules at 100% except `intent.py` (96%) and `validator.py` (93%).
- Test runner is `tasks.ps1` (Windows-first) with `test` and `cov` targets; documented in the README.
