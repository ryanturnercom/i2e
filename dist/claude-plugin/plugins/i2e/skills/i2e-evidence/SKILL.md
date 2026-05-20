---
name: i2e-evidence
description: For each evidence item and constraint in a capability, invoke its provider and record the verdict. Writes runs/<id>.yaml + current.yaml. Does not modify code.
license: Apache-2.0
metadata:
  tier: loop
  version: "0.1.0"
---

# i2e-evidence

The collector step of the loop. Given a Capability, walks every evidence item
and every constraint, invokes the named provider for each, and records the
verdict — a per-run immutable snapshot plus a rewritten `current.yaml`.

This skill never writes code. It is safe to re-invoke at any time; in
particular, re-runs across an `awaiting_human` item silently pick up the
resolution from `.i2e/pending/` when the human has answered, and leave the
verdict unchanged when they haven't.

## When to use
- After `i2e-develop` makes a change
- For periodic target re-evaluation (window elapsed)
- Standalone smoke check requested by user

## Inputs
- `capability` (required)
- `items` (optional, default = all): subset of item ids to re-evaluate

## Outputs
- `.i2e/evidence/<cap>/runs/<run-id>.yaml` (immutable snapshot)
- `.i2e/evidence/<cap>/current.yaml` (rewritten)
- Summary returned to orchestrator: `{pass: N, fail: N, met: N, unmet: N, awaiting: N}`

## Boundaries
- READ: `.i2e/intents/<cap>.md`, `.i2e/evidence/<cap>/current.yaml`, src/**
- WRITE: `.i2e/evidence/<cap>/**`, `.i2e/pending/**` (only via async providers),
  `.i2e/logs/**` (only when archiving a resolved pending file)
- NEVER WRITE: src/**, .i2e/intents/**

## Workflow
1. Load capability + validate (forced evidence check)
2. Resolve providers for every item + constraint
3. Generate a `run_id`
4. For each item: invoke provider → translate to `ItemVerdict` (carry over
   `attempts_used` from prior current.yaml for non-passing verdicts)
5. Write `runs/<run-id>.yaml` (immutable; will fail if id collides)
6. Rewrite `current.yaml` atomically
7. Return summary

## Async / pending lifecycle
- A provider may return `awaiting_human` and write a pending file under
  `.i2e/pending/`. The runner records `verdict="awaiting_human"` with a
  pointer to the pending basename. `attempts_used` is NOT incremented.
- The runner is safe to re-invoke. If the pending file is still `open`, the
  async provider will raise `FileExistsError`; the runner catches it, reads
  the existing pending file, and re-emits the same `awaiting_human` verdict
  (no second pending file is written).
- When the human resolves the pending file (`status: resolved`,
  `resolution: yes|no|partial`), the runner translates that into a real
  Case verdict, archives the pending file to `.i2e/logs/`, and the next
  evidence run will record `pass` or `fail` accordingly.

## Python helpers (the deterministic core)
- `i2e_core.evidence_runner.run(root, capability, only_items=None) -> RunSummary`
- `i2e_core.evidence_runner.reconcile(root, capability) -> CurrentEvidence`
- `i2e_core.evidence.read_current(root, capability) -> CurrentEvidence | None`
- `i2e_core.pending.resolve_to_verdict(pf) -> ItemVerdict`

## CLI helper
- `python -m i2e_core.evidence_runner <capability>` — runs the collection
  and prints the `RunSummary` as JSON. Exits 0 on success, 1 on validation
  failure.
