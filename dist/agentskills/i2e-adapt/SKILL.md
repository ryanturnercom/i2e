---
name: i2e-adapt
description: Inspect current.yaml; for non-passing items, either spend budget on another develop+evidence cycle or escalate to a pending file. Also applies resolved pendings back to intents.
license: Apache-2.0
metadata:
  tier: loop
  version: "0.1.0"
---

# i2e-adapt

The loop's brain. Reads `current.yaml`, finds items whose verdict is
`fail`, `unmet`, or `trending`, and decides — based on each item's `effort`
tier (spec §2.3) — whether to spend another auto-improvement attempt on it
or escalate to a human via a pending file (spec §6.2).

`i2e-adapt` also owns the resolution applier: when a human has resolved an
escalation pending file (`status: resolved`), the applier translates the
chosen path back into the intent file (or `current.yaml`) and archives the
pending file into `.i2e/logs/`.

## When to use
- Orchestrator's decision tree branch 3 (trending/unmet items with budget remaining)
- Orchestrator's decision tree branch 1 (apply resolved pendings) calls
  `i2e_core.adapt.apply_resolutions` directly

## Inputs
- `capability` (required)

## Outputs
- Either signals "retry develop+evidence" with the next attempt counter
- Or writes `.i2e/pending/<date>-<cap>-<id>.yaml` (escalation)

## Workflow
1. Read `current.yaml`
2. For each non-passing item (verdict in fail / unmet / trending):
   a. Look up effort tier → `max_attempts`
   b. If `attempts_used < max_attempts` ⇒ propose a code/intent change rationale; signal retry
   c. Else ⇒ write escalation pending file with the 3-most-recent attempts and a 4-option `ask:`
3. Return a summary to the orchestrator

## Boundaries
- READ: everything under `.i2e/`
- WRITE: `.i2e/pending/**`, `.i2e/logs/**` (tick log writer)
- NEVER WRITE: `src/**`
- **Intent-file carve-out**: `i2e-intent` is normally the ONLY skill that
  writes to `.i2e/intents/`. `i2e_core.adapt.apply_resolutions` is the
  single, gated exception: it is callable only from the orchestrator's
  preflight branch 1 (apply resolved pendings), uses
  `i2e_core.intent.write_intent` for atomicity, and is restricted to the
  four resolution shapes defined in spec §6.2 (loosen / new approach /
  retire / accept). Resolution choice 4 (accept) writes only to
  `current.yaml`; the intent file is untouched.

## Python helpers (the deterministic core)
- `i2e_core.adapt.plan(root, capability) -> AdaptPlan`
- `i2e_core.adapt.escalate(root, capability, item_id) -> Path`
- `i2e_core.adapt.has_open_escalation(root, capability, item_id) -> bool`
- `i2e_core.adapt.apply_resolutions(root) -> list[ResolutionApplied]`
- `i2e_core.tick_log.write_tick(root, tick) -> Path | None`
- `i2e_core.tick_log.latest_tick_for(root, capability, item_id=None) -> TickLog | None`
- `i2e_core.tick_log.changes_since(root, capability, item_id, n=3) -> list[tuple[str, str]]`
