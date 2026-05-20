---
name: i2e-provider-human
description: Collect subjective human acceptance for a Case or Target. Writes a pending file and returns awaiting_human; the resolution is applied on a later orchestrator tick.
license: Apache-2.0
metadata:
  tier: provider
  version: "0.1.0"
---

# i2e-provider-human

Async provider. First call writes `.i2e/pending/<date>-<cap>-<id>.yaml` and returns `awaiting_human`. The orchestrator's preflight picks up `status: resolved` files and applies them.

## Inputs
- `query` — the prompt to show the human
- `expect` — typically `yes` (also: `no`, `partial`, or a free string)

## Returns
- `{ verdict: "awaiting_human", pending: "<basename>" }` on first ask
