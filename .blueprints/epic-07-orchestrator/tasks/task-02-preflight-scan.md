# Task: Preflight validation scan

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-01-skill-manifest, task-04-intent-validator (epic 01)

## Context

Spec §5 says validation runs on every intent edit AND on every orchestrator tick. Preflight is the second guardrail — even if an intent file is hand-edited (bypassing `i2e-intent`), the orchestrator catches it.

## Needed from User

None.

## Instructions

1. Implement `src/i2e_core/orchestrator.py::preflight(root) -> PreflightResult`:
   - `PreflightResult(BaseModel)`: `valid: bool`, `errors: dict[str, list[str]]` (keyed by capability slug)
   - Walks every `.i2e/intents/*.md` with `status == "active"`
   - For each: `parse_intent` → `validate_capability_with_config` with installed providers
   - Aggregates errors per capability
   - Returns `valid=True` only when every capability validates clean
2. If preflight fails, `tick` raises `PreflightFailed(result)` and the orchestrator skill exits with code 1
3. `draft` intents are skipped (they're work-in-progress; the user knows)
4. `retired` intents are skipped (they're frozen by definition)

## Acceptance Criteria

- [x] Preflight passes with valid intents
- [x] Preflight fails when any active intent has an unknown provider
- [x] Preflight fails when any active intent has zero items
- [x] Draft and retired intents do not trigger preflight failures
- [x] Errors are aggregated across all intents (not first-fail)

## Implementation Notes

- `PreflightResult` is a Pydantic v2 model with `valid: bool` and
  `errors: dict[str, list[str]]` keyed by capability slug.
- `preflight(root)` walks `.i2e/intents/*.md` in alphabetical order. For
  each `status: active` intent it runs `validate_capability_with_config`
  against the loaded `I2EConfig` and the set returned by
  `installed_provider_names()`.
- Parse failures are themselves recorded as errors (under the file stem)
  rather than crashing — preflight is best-effort batched.
- Drafts and retired intents are skipped, so a draft with an unknown
  provider does NOT block the tick.
- `PreflightFailed(result)` renders a multi-line message listing every
  capability and its errors; the CLI prints this to stderr on exit 1.
