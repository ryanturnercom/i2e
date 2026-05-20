---
name: i2e-provider-sentry
description: Query Sentry for event counts; emit a Case (constraint, expect=0) or Target (expect=<N) verdict.
license: Apache-2.0
metadata:
  tier: provider
  version: "0.1.0"
---

# i2e-provider-sentry
Reads `SENTRY_AUTH_TOKEN`, `SENTRY_ORG_SLUG`, `SENTRY_PROJECT_SLUG`. Fails fast with a clear message if env vars are missing.

## Inputs
- `query`: Sentry search query (passed as `?query=`)
- `window`: e.g. `5m`, `24h`, `7d` (defaults to `24h`)
- `expect`:
  - `0` → constraint shape; ``pass`` iff count == 0
  - `<N`, `<=N`, etc. → target shape with value = count

## Returns
- `CaseResult` for `expect: 0`
- `TargetResult` for any comparison expression
