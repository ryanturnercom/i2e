---
name: i2e-provider-human
description: Collect subjective human acceptance for a Target. Writes a pending file and returns awaiting_human; the resolution is applied on a later orchestrator tick.
license: Apache-2.0
metadata:
  tier: provider
  version: "0.1.0"
---

# i2e-provider-human

Async provider, **target items only** — a human verdict cannot be produced synchronously, so a human-judged item is always a target (spec §2.2). First call writes `.i2e/pending/<date>-<cap>-<id>.yaml` and returns `awaiting_human`. The orchestrator's preflight picks up `status: resolved` files and applies them. On resolution: `yes` → `met`, `no` → `unmet`, `partial` → `trending`.

## Inputs
- `query` — the prompt to show the human
- `expect` — typically `yes` (also: `no`, `partial`, or a free string)

## Returns
- `{ verdict: "awaiting_human", pending: "<basename>" }` on first ask
