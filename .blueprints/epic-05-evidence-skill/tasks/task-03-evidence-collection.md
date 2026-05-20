# Task: Snapshot + current.yaml writer

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-02-provider-invocation, task-05-evidence-writer (epic 01)

## Context

The writer pieces (`write_run_snapshot`, `write_current`) live in `i2e_core.evidence`. This task wires the runner to them and adds the integrity properties:

- `runs/<id>.yaml` is immutable (refuse to overwrite)
- `current.yaml` is always derived from the latest snapshot — no drift
- Both writes are atomic (no partial files)

## Needed from User

None.

## Instructions

1. Verify the wiring from `evidence_runner.run` to `write_run_snapshot` and `write_current` does NOT mutate the snapshot after writing (sanity)
2. Add `def reconcile(root: Path, capability: str) -> CurrentEvidence`:
   - Rebuilds `current.yaml` from the most recent `runs/*.yaml` (used as a recovery tool if current.yaml is lost/corrupted)
3. Add a CLI helper `python -m i2e_core.evidence_runner <capability>` that runs the evidence collection and prints the `RunSummary` as JSON

## Acceptance Criteria

- [x] `runs/<id>.yaml` is never re-written after first creation (test: second run with same id raises)
- [x] After `run`, `current.yaml` reflects the new snapshot byte-for-byte (verdicts match)
- [x] `reconcile` reproduces the same `current.yaml` from the latest snapshot
- [x] CLI helper exits 0 on success and 1 if validation fails

## Implementation Notes

- `write_run_snapshot` (already in `i2e_core.evidence`) raises
  `FileExistsError` on overwrite — confirmed via a runner-level test that
  forces the same run-id via `monkeypatch` on `evidence_runner.new_run_id`.
- The runner constructs `RunSnapshot` and `CurrentEvidence` from the
  same `verdicts` dict, then hands them to the writers. We never mutate
  the dict after `write_run_snapshot` succeeds.
- Added `reconcile(root, capability) -> CurrentEvidence` that finds the
  most-recent `runs/*.yaml` and writes a fresh `current.yaml` from it.
  Picks the most recent file by `stat().st_mtime` rather than relying
  on the alphabetical order returned by `list_runs`, because same-day
  run-ids use a random hex suffix so alphabetical order does NOT match
  write order.
- Added the CLI helper `python -m i2e_core.evidence_runner <capability>`
  using stdlib `argparse`. Accepts `--root` and repeatable `--only`
  flags. Prints the `RunSummary` as JSON via
  `summary.model_dump(by_alias=True)` so the `"pass"` key appears
  unquoted-as-keyword. Returns exit 0 on success, 1 on `ValidationError`.
- Verified via `test_reconcile.py` that deleting `current.yaml` and
  calling `reconcile` reproduces the same items / last_run / intent_version
  as the pre-deletion snapshot.
