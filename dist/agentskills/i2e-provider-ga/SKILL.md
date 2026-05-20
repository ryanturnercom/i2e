---
name: i2e-provider-ga
description: Query GA4 Data API for a metric value over a window; compare against expect. Returns a Target verdict.
license: Apache-2.0
metadata:
  tier: provider
  version: "0.1.0"
---

# i2e-provider-ga
Reads `GA_PROPERTY_ID`, `GA_SERVICE_ACCOUNT_JSON_PATH`. Requires the optional
`ga` extra: `pip install i2e_core[ga]`.

## Inputs
- `query`: JSON string like `{"metric": "eventCount", "dimensions": ["eventName"], "filter": "..."}`
- `window`: GA dateRange `startDate` (e.g. `7daysAgo`, `today`); maps to `(startDate, "today")`
- `expect`: comparison expression (`<NUM[unit]`, etc.) — same parser as Datadog

## Returns
- `{ value: "<num>", met: "met"|"unmet"|"trending", observed_at: <iso> }`
