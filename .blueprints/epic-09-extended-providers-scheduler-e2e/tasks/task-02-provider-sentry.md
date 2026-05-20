# Task: i2e-provider-sentry

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-01-provider-contract (epic 02)

## Context

Sentry provider for Constraint or Target evidence — typical use is "PII not logged" (constraint, expects 0 events matching a search) or error-rate target.

Spec example:
```yaml
- id: pii-not-logged
  provider: sentry
  query: events:contains("http") in:logs
  expect: 0
```

## Needed from User

- `SENTRY_AUTH_TOKEN`: Sentry API token with `event:read` scope.
- `SENTRY_ORG_SLUG`: Sentry organization slug.
- `SENTRY_PROJECT_SLUG`: Sentry project slug.

## Instructions

1. Create `.claude/skills/i2e-provider-sentry/SKILL.md` (manifest with the env vars listed above)
2. Create `provider.py`:
   - Calls `GET /api/0/projects/{org}/{project}/events/?query=<query>&statsPeriod=<window>`
   - `expect: 0` → constraint shape (`pass` if count==0, `fail` otherwise)
   - `expect: <N` → target shape with value = count
   - `window` defaults to `24h` if absent
3. Use `urllib.request`; surface HTTP errors as Provider exceptions (caught by runner as `fail`)

## Acceptance Criteria

- [x] Skill discovered as `sentry`
- [x] Missing env vars → clear `RuntimeError`
- [x] `expect: 0` returns `CaseResult` (constraint shape) with `pass` when count is 0
- [x] `expect: <100` returns `TargetResult` with `met` when count below threshold
- [x] HTTP 401/403 produces an actionable error message naming the token env var

## Implementation Notes

- Created `.claude/skills/i2e-provider-sentry/{SKILL.md,provider.py}`.
- Detection of "constraint vs target" shape is literal: `expect.strip() == "0"`
  → `CaseResult`; any other shape goes through `parse_expect` and emits a
  `TargetResult`.
- HTTP via stdlib `urllib.request`; tests mock `urlopen`.
- 401/403 errors raise `RuntimeError` mentioning `SENTRY_AUTH_TOKEN`; any
  other HTTP error includes the upstream body (truncated to 200 chars).
- Endpoint shape supports both `[…]` and `{"data": […]}` payloads (Sentry
  varies by endpoint).
- Tests: `tests/providers/test_sentry_provider.py` (10 tests).
