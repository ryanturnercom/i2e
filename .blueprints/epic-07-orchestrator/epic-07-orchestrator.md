# Epic: i2e Orchestrator Skill

**Status:** [✓] Completed
**Source spec:** .documentation/I2E_simplified.md
**Started:** 2026-05-19
**Completed:** 2026-05-19

## Context

`i2e` is the front door. A human (or a scheduler) invokes it; it runs a preflight scan and advances the project by exactly one step.

Decision tree (spec §6.1, ordered — first match wins):

1. Any `pending/` file with `status: resolved`? → apply resolution, archive
2. Any active intent with no matching evidence (new or version-bumped)? → develop + evidence
3. Any `current.yaml` showing trending/unmet items with budget remaining? → adapt → develop + evidence
4. Any target whose window has elapsed since `last_observed`? → re-evidence just that item
5. All Capabilities green? → mark shippable; do nothing

After any state-changing step, `i2e-report` is invoked so `.i2e/report.html` is always fresh.

## Implementation Overview

- Ship a SKILL.md at `~/.claude/skills/i2e/SKILL.md`
- Preflight: re-runs forced-evidence validation across all active intents; halts the tick with a clear error if any intent is invalid
- Decision tree implemented as five ordered checks against `.i2e/` state
- A "one-step advance" runner that delegates to the appropriate loop skill, then unconditionally invokes `i2e-report`
- Tick log entry is appended only when the tick actually did something (empty ticks are silent — spec §9)

## Tasks

- [x] [task-01: SKILL.md manifest for i2e](tasks/task-01-skill-manifest.md)
- [x] [task-02: Preflight validation scan](tasks/task-02-preflight-scan.md)
- [x] [task-03: Decision tree evaluator](tasks/task-03-decision-tree.md)
- [x] [task-04: One-step advance + report invocation](tasks/task-04-step-advance.md)
- [x] [task-05: Tests for each decision branch](tasks/task-05-tests.md)

## Outcome

**Shipped:**
- `.claude/skills/i2e/SKILL.md` — manifest mirroring spec §6.1's 5-branch
  decision tree with explicit boundaries and CLI exit-code contract.
- `src/i2e_core/orchestrator.py` — `preflight`, `decide`, `tick`,
  `parse_window`, plus Pydantic v2 `PreflightResult`, `TickResult`, and
  the discriminated `Action` union (`ApplyResolutions`,
  `DevelopAndEvidence`, `AdaptThenRetry`, `ReEvaluateItem`,
  `Shippable`). `PreflightFailed` exception. CLI entry point
  `python -m i2e_core.orchestrator` with exit codes 0/1/2.
- `src/i2e_core/report/__init__.py` — minimal `render(root) -> None`
  stub for epic 08 to replace, plus `templates/.gitkeep`.
- `tests/orchestrator/` — 36 tests across `test_preflight.py` (7),
  `test_decide.py` (16), `test_tick.py` (9), `test_cli.py` (4), plus a
  shared `conftest.py` with provider-fake helpers.

**Gate:**
- `.venv\Scripts\python.exe -m pytest -q` → **256 passed** (220 existing
  + 36 new).
- Coverage: 93% overall; `orchestrator.py` 89%, `report/__init__.py` 80%
  (stub is a single uncovered return on epic-08's behalf). Above the
  ≥85% threshold for `orchestrator.py`.

**Notes:**
- Develop and adapt-retry are LLM-driven on the action side; the
  orchestrator's deterministic core handles validation, planning,
  evidence runs, escalation file writes, logging, and reporting. The
  next tick converges naturally — no subprocess hook is needed in the
  loop.
- `decide` walks capabilities alphabetically for determinism.
- Branch 4 (`ReEvaluateItem`) skips items missing `window` or
  `last_observed`, and tolerates naive datetimes by coercing to UTC.
- The action union uses Pydantic v2 with a `Literal[...]` `kind`
  discriminator so JSON round-trips cleanly out of the CLI.
- Empty ticks remain silent (spec §9): no `*-tick.yaml` written, no
  report rendered.
