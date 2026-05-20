# Task: Scheduler integration helper

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-04-step-advance (epic 07)

## Context

Spec §6.3 — BYO scheduler. Ship a first-run helper that:

- Detects Claude Code CLI presence
- Offers to register a `/schedule` routine that calls `i2e` on the configured cadence (`scheduler.cadence` from config)
- Otherwise prints copy-paste templates for Windows Task Scheduler, launchd, and cron

## Needed from User

None (the helper is interactive but does not require credentials).

## Instructions

1. Add `src/i2e_core/scheduler.py`:
   - `def detect_claude_code() -> bool` — checks `shutil.which("claude")`
   - `def suggest_registration(root: Path) -> str` — returns a one-line `claude /schedule "Run i2e" --cwd <abs path> --cadence <cadence>` command
   - `def os_scheduler_templates(root: Path) -> dict[str, str]` — returns a dict with keys `windows`, `launchd`, `cron`; each value is a fully-rendered config snippet pointing at this project
2. Add a CLI entry: `python -m i2e_core.scheduler suggest`
3. Document in the project README that the helper is opt-in — `i2e` itself does not install any scheduler

## Acceptance Criteria

- [x] `detect_claude_code` returns True/False based on `shutil.which`
- [x] `suggest_registration` produces a valid Claude Code `/schedule` command line
- [x] `os_scheduler_templates` returns non-empty strings for all three OSes
- [x] CLI prints the templates clearly with section headers

## Implementation Notes

- Added `src/i2e_core/scheduler.py` with:
  - `detect_claude_code()` — wraps `shutil.which("claude")`
  - `suggest_registration(root, cadence=None)` — returns a one-line
    `claude /schedule "Run i2e" --cwd "..." --cadence <c>` command, picking
    the cadence from `<root>/.i2e/config.yaml` when absent
  - `os_scheduler_templates(root, cadence=None)` — returns `{windows,
    launchd, cron}` strings, each fully-rendered for the project path and
    the current Python interpreter
- Cadence-to-cron / Windows-flag mappings cover `hourly`, `daily`, `weekly`,
  `monthly`; unknown cadences fall back to weekly (no exception).
- CLI: `python -m i2e_core.scheduler suggest [--root PATH] [--cadence X]`.
  Prints Claude Code suggestion (if detected) and all three OS templates
  with section headers.
- The helper never installs schedulers — it only prints templates.
- Tests: `tests/test_scheduler.py` (11 tests).
