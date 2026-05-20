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
