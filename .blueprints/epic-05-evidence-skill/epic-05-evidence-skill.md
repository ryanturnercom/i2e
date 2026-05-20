# Epic: i2e-evidence Skill

**Status:** [✓] Completed
**Source spec:** .documentation/I2E_simplified.md
**Started:** 2026-05-19
**Completed:** 2026-05-19

## Context

`i2e-evidence` is the collector. For every evidence item and constraint in a Capability, it invokes the named provider and writes the result.

Output shape (spec §7):

```
.i2e/evidence/<capability>/
├── current.yaml        # always-rewritten; latest verdict per item
└── runs/
    └── <run-id>.yaml   # immutable per-run snapshot
```

Verdicts come in three shapes: Case pass/fail, Target value/met, async awaiting_human.

## Implementation Overview

- Ship a SKILL.md at `~/.claude/skills/i2e-evidence/SKILL.md`
- A runner that, given a capability:
  1. Loads the intent, validates it (forced-evidence check)
  2. For each item + constraint: resolves the provider, invokes it, captures the verdict
  3. Writes a new `runs/<run-id>.yaml` snapshot with the full verdict set
  4. Rewrites `current.yaml` from the new snapshot
  5. Returns a summary the orchestrator can use to pick the next step
- Async verdicts (`awaiting_human`) are recorded in `current.yaml` with a pointer to the pending file; they do not block the rest of the run

This epic depends on the provider contract from epic 02 being final.

## Tasks

- [x] [task-01: SKILL.md manifest for i2e-evidence](tasks/task-01-skill-manifest.md)
- [x] [task-02: Provider invocation loop](tasks/task-02-provider-invocation.md)
- [x] [task-03: Snapshot + current.yaml writer](tasks/task-03-evidence-collection.md)
- [x] [task-04: Async verdict handling (awaiting_human)](tasks/task-04-async-pending.md)
- [x] [task-05: Tests for the evidence runner](tasks/task-05-tests.md)

## Outcome

- Skill manifest shipped at `.claude/skills/i2e-evidence/SKILL.md` with
  explicit READ / WRITE / NEVER-WRITE boundaries (forbids `src/**` and
  `.i2e/intents/**`).
- Deterministic runner at `src/i2e_core/evidence_runner.py` exposes:
  - `run(root, capability, only_items=None) -> RunSummary` — full
    provider invocation loop with validation preflight, per-item
    exception capture, only_items carry-over, immutable
    `runs/<id>.yaml` writes, atomic `current.yaml` rewrites
  - `reconcile(root, capability) -> CurrentEvidence` — recovery tool
    that rebuilds `current.yaml` from the most-recently-modified run
    snapshot
  - CLI: `python -m i2e_core.evidence_runner <capability>` prints
    `RunSummary` JSON; exits 0 on success, 1 on validation failure
- `RunSummary` Pydantic v2 model uses `Field(0, alias="pass")` +
  `populate_by_name=True` so callers can write `summary.pass_` in
  Python and the YAML/JSON form uses the literal `pass` key.
- `RunSummary.compact()` returns the one-line tick-log form
  `"<n> pass, <n> trending, <n> fail"`.
- Async lifecycle: first invocation writes a pending file and records
  `awaiting_human` (no attempts bump). Re-runs catch
  `FileExistsError` from the async provider, read the existing
  pending file, and either re-emit the same `awaiting_human` (still
  open) or translate the resolution into a real verdict + archive the
  pending file to `.i2e/logs/`.
- `resolve_to_verdict(pf)` lives in `pending.py` next to the model.
  Handles `kind="human_evaluation"` for yes / no / partial. Survey
  numeric resolutions and `kind="escalation"` raise — they belong to
  epic 09 (surveys) and epic 06 (adapt) respectively.
- Tests: 27 new tests in `tests/evidence/`, all green. Whole suite
  183 tests pass in ~1.2s. Coverage 96% (evidence_runner 93%,
  pending 98%, evidence 100%). Uncovered lines are defensive
  fallback branches.
