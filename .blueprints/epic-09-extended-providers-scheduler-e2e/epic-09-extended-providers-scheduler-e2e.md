# Epic: Extended Providers, Scheduler Integration, End-to-End

**Status:** [x] Complete
**Source spec:** .documentation/I2E_simplified.md
**Started:** 2026-05-19
**Completed:** 2026-05-19

## Context

With the loop skills and core providers in place, this epic broadens the provider registry, wires the scheduler, and validates the whole system end-to-end via the spec's worked example (§10 — "bug becomes a Case").

Providers in scope: `datadog`, `sentry`, `ga` (Google Analytics), and `survey`. The first three are Target-shape providers (return `value` + `met` + `observed_at`). `survey` reuses the async pending pattern from `i2e-provider-human`.

Scheduler: BYO per the spec, but ship a first-run helper that registers a Claude Code `/schedule` routine for the orchestrator.

## Implementation Overview

- Four provider skills, each with SKILL.md + a Python helper
- Datadog/Sentry/GA use HTTP clients with API tokens from env vars (documented in each task's "Needed from User")
- Survey: writes a pending file with `kind: human_evaluation`, multiple-choice `verdict_options`
- Scheduler helper: detects Claude Code CLI is available, suggests `/schedule` registration; falls back to printing OS-scheduler templates
- End-to-end smoke test: scripted walkthrough of the password-bug worked example — author intent, run `i2e` to green, verify the bug cannot recur

## Tasks

- [x] [task-01: i2e-provider-datadog](tasks/task-01-provider-datadog.md)
- [x] [task-02: i2e-provider-sentry](tasks/task-02-provider-sentry.md)
- [x] [task-03: i2e-provider-ga](tasks/task-03-provider-ga.md)
- [x] [task-04: i2e-provider-survey](tasks/task-04-provider-survey.md)
- [x] [task-05: Scheduler integration helper](tasks/task-05-scheduler-integration.md)
- [x] [task-06: End-to-end smoke test (worked example)](tasks/task-06-end-to-end-smoke.md)

## Outcome

- Default suite: **358 passed, 1 deselected (e2e)** in ~4.8s.
- E2E suite: `pytest -m e2e` → **1 passed** in ~1.4s.
- Coverage on `src/i2e_core/`: **91%** (line+branch), well above the 85% gate.
- Four new provider skills are discoverable and importable:
  - `.claude/skills/i2e-provider-datadog/` — stdlib `urllib`, mocked tests
  - `.claude/skills/i2e-provider-sentry/`  — stdlib `urllib`, mocked tests
  - `.claude/skills/i2e-provider-ga/`      — lazy-imports the optional
    `google.*` libs; tests inject fakes into `sys.modules`
  - `.claude/skills/i2e-provider-survey/`  — async pending; numeric scales
- Shared parser: `src/i2e_core/provider/expect_parser.py` (`parse_expect`,
  `compare`, `is_trending`) used by datadog and ga; survey's resolver also
  uses it for numeric resolutions.
- `i2e_core.pending.resolve_to_verdict` extended for numeric resolutions
  (the survey path). Backward compatible — yes/no/partial still work.
- `src/i2e_core/scheduler.py` exposes `detect_claude_code`,
  `suggest_registration`, `os_scheduler_templates`, and a CLI entry
  (`python -m i2e_core.scheduler suggest`).
- `pyproject.toml`:
  - `[project.optional-dependencies] ga = ["google-auth>=2", "google-analytics-data>=0.18"]`
  - `[tool.pytest.ini_options] markers = ["e2e: ..."]` + `-m 'not e2e'`
    in `addopts` so the default invocation excludes the e2e marker.
- E2E worked example reproduces spec §10 deterministically: buggy
  `change_password.is_valid_password` → 3 failing tests → adapt plans
  retries → develop simulator fixes the validator → re-run is all green
  → orchestrator returns `Shippable` → report HTML shows `shippable=True`.
- No real HTTP requests are made by any test; no schedulers are installed.
