---
name: i2e-provider-survey
description: Ask a human a numeric-scale survey question (NPS 0-10 / Likert 1-5). Writes a pending file and returns awaiting_human.
license: Apache-2.0
metadata:
  tier: provider
  version: "0.1.0"
---

# i2e-provider-survey

Asynchronous provider. First call writes `.i2e/pending/<date>-<cap>-<id>.yaml`
with numeric `verdict_options` and returns `awaiting_human`. The
orchestrator's preflight picks up `status: resolved` files and translates
the numeric resolution into a Target verdict using the item's `expect`.

## Inputs
- `query` — JSON object with at least:
  - `prompt`: the question shown to the human
  - `scale`: `"nps"` (0-10) or `"likert"` (1-5). Default: `"nps"`.
  - `followup` (optional): free-text follow-up question
- `expect` — a comparison expression like `">=8"` (NPS promoters) or `">=4"`
  (Likert agreement). Same parser as the datadog/ga providers.

## Returns
- `{ verdict: "awaiting_human", pending: "<basename>" }` on first ask
- On resolution: a `TargetResult` synthesised by `pending.resolve_to_verdict`
