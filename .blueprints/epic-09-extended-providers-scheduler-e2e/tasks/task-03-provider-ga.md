# Task: i2e-provider-ga

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-01-provider-contract (epic 02)

## Context

Google Analytics provider for Target evidence — funnel metrics, page events. Uses GA4 Data API.

## Needed from User

- `GA_PROPERTY_ID`: GA4 property ID (numeric).
- `GA_SERVICE_ACCOUNT_JSON_PATH`: Path to a Google service account JSON file with `analytics.viewer` role on the property.

## Instructions

1. Create `.claude/skills/i2e-provider-ga/SKILL.md`
2. Create `provider.py`:
   - Auth via the service account JSON (use `google-auth` + `google-analytics-data` if installed; otherwise raise with install instructions)
   - `query` is a JSON object: `{"metric": "eventCount", "dimensions": ["eventName"], "filter": "..."}`
   - `window` → GA `dateRange.startDate` (e.g. `7daysAgo`)
   - `expect` parsed like the Datadog provider
3. Add `google-auth` and `google-analytics-data` as **optional** dependencies in `pyproject.toml` (`[project.optional-dependencies] ga = [...]`) — keeps the core install lean

## Acceptance Criteria

- [x] Skill discovered as `ga`
- [x] Importing the provider without `google-analytics-data` installed raises a clear `RuntimeError` with `pip install i2e_core[ga]` instruction
- [x] With mocked GA client, returns `TargetResult` with the metric value
- [x] `expect` parser shared with datadog (refactor into `i2e_core.provider.expect_parser` if not already)

## Implementation Notes

- Created `.claude/skills/i2e-provider-ga/{SKILL.md,provider.py}`.
- Lazy-imports `google.oauth2.service_account`,
  `google.analytics.data_v1beta`, and its `types` submodule INSIDE
  `_run_query`. ImportError surfaces as `RuntimeError(... pip install
  i2e_core[ga])`. The optional deps are NOT required for normal install.
- Added `[project.optional-dependencies] ga = ["google-auth>=2",
  "google-analytics-data>=0.18"]` to `pyproject.toml`.
- `query` accepts a JSON object (string) with at least `metric` and optional
  `dimensions`. The provider sums all rows × metric_values to handle
  multi-dimension queries gracefully.
- Window is interpreted as the GA `startDate` (e.g. `7daysAgo`); `endDate`
  is always `today`.
- Tests use `sys.modules` injection to fake the google packages — no real
  packages are required. Tests: `tests/providers/test_ga_provider.py`
  (9 tests).
