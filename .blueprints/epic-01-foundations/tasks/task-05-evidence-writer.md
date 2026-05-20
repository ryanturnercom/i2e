# Task: Evidence read/write (current.yaml + runs/)

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-03-intent-parser, task-06-shared-utils

## Context

Spec §7 defines the evidence layout per capability:

```
.i2e/evidence/<capability>/
├── current.yaml        # always-rewritten; latest verdict per item
└── runs/
    └── <run-id>.yaml   # immutable per-run snapshot
```

`current.yaml` carries `intent_version`, `last_run`, and a per-item verdict map. Per-run files carry the full snapshot with `collected_at` and raw provider output.

## Needed from User

None.

## Instructions

1. Create `src/i2e_core/evidence.py` with Pydantic models:
   - `ItemVerdict(BaseModel)`: `verdict: Literal["pass","fail","met","unmet","trending","awaiting_human"]`, plus optional `value: str | None`, `attempts_used: int = 0`, `last_observed: datetime | None`, `pending: str | None` (pending-file basename), `raw: dict[str, Any] = {}`
   - `CurrentEvidence(BaseModel)`: `capability: str`, `last_run: str`, `intent_version: int`, `items: dict[str, ItemVerdict]`
   - `RunSnapshot(BaseModel)`: `run_id: str`, `capability: str`, `intent_version: int`, `collected_at: datetime`, `items: dict[str, ItemVerdict]`
2. I/O functions:
   - `read_current(root: Path, capability: str) -> CurrentEvidence | None`
   - `write_current(root: Path, cap: CurrentEvidence) -> Path` — atomic
   - `write_run_snapshot(root: Path, snap: RunSnapshot) -> Path` — atomic, refuses to overwrite (immutable)
   - `list_runs(root: Path, capability: str) -> list[Path]` — sorted by run-id (which is date-prefixed)
   - `read_run(path: Path) -> RunSnapshot`
3. Emit YAML with stable key order and block-style lists. Use `yaml.safe_dump(..., sort_keys=False)`.
4. The directory is created lazily on first write (`mkdir(parents=True, exist_ok=True)`).

## Acceptance Criteria

- [✓] `write_current` overwrites atomically (no partial file on crash)
- [✓] `write_run_snapshot` raises `FileExistsError` if `runs/<id>.yaml` already exists
- [✓] `list_runs` returns paths in chronological order (oldest first)
- [✓] Round-trip: `read_current(...) == CurrentEvidence.model_validate(yaml.safe_load(open(...).read()))`
- [✓] Reading a missing `current.yaml` returns `None` (not an exception)

## Implementation Notes

- `src/i2e_core/evidence.py` defines `ItemVerdict`, `CurrentEvidence`, `RunSnapshot` plus `read_current`, `write_current`, `write_run_snapshot`, `list_runs`, and `read_run`.
- All writes go through `io_utils.atomic_write`; `write_run_snapshot` refuses overwrite (immutable per-run snapshots).
- `Verdict` literal covers `pass`, `fail`, `met`, `unmet`, `trending`, `awaiting_human`.
- Directories are created lazily on first write (`mkdir(parents=True, exist_ok=True)`).
