# Epic: i2e-develop Skill

**Status:** [✓] Completed
**Source spec:** .documentation/I2E_simplified.md
**Started:** 2026-05-19
**Completed:** 2026-05-19

## Context

`i2e-develop` builds the System in `src/` from the current `active` intents. It is the only loop skill that writes production code.

Key constraints:
- Reads `.i2e/context/` (standing reference like ARCHITECTURE.md, DESIGN.md) but never has to prove it
- Writes only to `src/` and `tests/` — not to `.i2e/`
- Tracks the last-developed intent version per capability so it knows what changed

## Implementation Overview

- Ship a SKILL.md at `~/.claude/skills/i2e-develop/SKILL.md`
- A workflow that, given a target capability (or "all stale"):
  1. Loads the intent file + `.i2e/context/*` reference docs
  2. Diffs against the last developed intent version (tracked in `.i2e/evidence/<cap>/current.yaml` → `intent_version`)
  3. Writes/updates code in `src/` and tests in `tests/` until the gap is closed
  4. Hands off to `i2e-evidence` (the orchestrator does the actual handoff — develop just signals done)

The skill does not run tests itself; that is `i2e-evidence`'s job. Develop's job is "make the code reflect the intent." A clean separation makes the loop simple to reason about.

## Tasks

- [✓] [task-01: SKILL.md manifest for i2e-develop](tasks/task-01-skill-manifest.md)
- [✓] [task-02: Context loader for .i2e/context/](tasks/task-02-context-loader.md)
- [✓] [task-03: Develop workflow (intent → src/)](tasks/task-03-develop-workflow.md)
- [✓] [task-04: Idempotency via intent_version](tasks/task-04-idempotency.md)
- [✓] [task-05: Tests for develop flow](tasks/task-05-tests.md)

## Outcome

All five tasks shipped, all tests green, coverage above the gate.

**Files created:**
- `.claude/skills/i2e-develop/SKILL.md`
- `src/i2e_core/context.py`
- `src/i2e_core/develop.py`
- `tests/develop/__init__.py`
- `tests/develop/conftest.py`
- `tests/develop/test_context_loader.py`
- `tests/develop/test_diff.py`
- `tests/develop/test_needs_develop.py`
- `tests/develop/test_paths.py`
- `tests/fixtures/context_seed/ARCHITECTURE.md`
- `tests/fixtures/context_seed/DESIGN.md`

**Test results:** 156 passed (115 prior + 41 new).
**Coverage:** `src/i2e_core/` overall **96%**; `i2e_core.develop` 95%,
`i2e_core.context` 94% — both well above the 85% threshold.

**Key design choices:**
- `DevelopDiff` is a Pydantic v2 `BaseModel` (consistent with the rest of the
  codebase), not a plain dataclass.
- "Changed items" are inferred from version bump, not item-body diff, because
  prior intents are not snapshotted on disk. The `current.yaml`'s `items` map
  is the only durable record of which item ids the system has accounted for.
- `load_context` truncates at document boundaries (omits whole files past the
  budget) rather than partial-appending — keeps each returned value a
  complete document, which is what the LLM expects.
- `suggested_test_paths` returns `None` for non-pytest providers; no
  general convention exists for human/datadog/sentry/etc.

**Boundary discipline:** Python helpers only do diffs, suggestions, and
idempotency checks. The LLM-side develop logic lives entirely in
`SKILL.md`'s Workflow section, per the brief.
