# Task: i2e-provider-datadog

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-01-provider-contract (epic 02)

## Context

Datadog provider for Target evidence — queries metric values and compares against the item's `expect` threshold. Example item:

```yaml
- id: redirect-latency-p95
  type: target
  provider: datadog
  query: redirect_latency{quantile=0.95}
  window: 5m
  expect: <50ms
```

## Needed from User

- `DATADOG_API_KEY`: Datadog API key with metric read scope. Used to query the timeseries.
- `DATADOG_APP_KEY`: Datadog Application key. Required alongside the API key.
- `DATADOG_SITE` (optional): Datadog site (`datadoghq.com` default, `datadoghq.eu`, etc.)

## Instructions

1. Create `.claude/skills/i2e-provider-datadog/SKILL.md`:
```markdown
---
name: i2e-provider-datadog
description: Query Datadog for a metric value over a window; compare against expect. Returns a Target verdict.
license: Apache-2.0
metadata:
  tier: provider
  version: "0.1.0"
---

# i2e-provider-datadog
Reads `DATADOG_API_KEY`, `DATADOG_APP_KEY`, optional `DATADOG_SITE`. Fails fast with a clear message if env vars are missing.

## Inputs
- `query`: Datadog metric query (passed to `/api/v1/query`)
- `window`: e.g. `5m`, `1h`, `7d`
- `expect`: comparison expression — `<NUM[unit]`, `>NUM[unit]`, `>=NUM[unit]`, `<=NUM[unit]`, `==NUM[unit]`

## Returns
- `{ value: "<num><unit>", met: "met"|"unmet"|"trending", observed_at: <iso> }`
```

2. Create `provider.py`:
   - Parse `expect` into `(op, threshold, unit)`
   - Call DD API for `query` over `now - window .. now`; take latest non-null value (or average per the metric's documented aggregation)
   - Compute `met` via the comparison; `trending` if value is within 10% of threshold in the right direction
   - Return `TargetResult`
3. Use `urllib.request` (no extra deps) for the HTTP call to keep the provider stdlib-only

## Acceptance Criteria

- [x] Skill discovered as `datadog`
- [x] Missing env vars → clear `RuntimeError` (not a stacktrace)
- [x] Mocked happy path (use `responses` or stdlib mock) returns `TargetResult` with `met="met"` when value beats threshold
- [x] `expect` parser handles `<50ms`, `>=99%`, `==0`
- [x] Trending margin: 10% within threshold direction triggers `trending`

## Implementation Notes

- Created `.claude/skills/i2e-provider-datadog/{SKILL.md,provider.py}`.
- Created shared parser at `src/i2e_core/provider/expect_parser.py` exporting
  `parse_expect`, `compare`, `is_trending` (10% margin by default). Datadog
  and GA both use it.
- HTTP via stdlib `urllib.request`; `urlopen` mocked in tests with
  `unittest.mock.patch`. No external requests are made.
- Returned value strings render integers without a trailing `.0` for clean
  evidence files (e.g. `"42ms"`, not `"42.0ms"`).
- Provider raises `RuntimeError` (not a bare stacktrace) on missing env vars
  and HTTP errors, with the response body included for upstream debugging.
- Tests: `tests/providers/test_datadog_provider.py` (10 tests) and
  `tests/providers/test_expect_parser.py` (17 tests).
