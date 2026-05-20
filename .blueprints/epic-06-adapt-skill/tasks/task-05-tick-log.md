# Task: Tick-log writer

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-06-shared-utils (epic 01)

## Context

Spec §9 — append-only, dated, signal-only. Empty ticks do not log. The tick log captures what the orchestrator did so adapt can reference "what changed since last time" when building an escalation's attempts list.

## Needed from User

None.

## Instructions

1. Create `src/i2e_core/tick_log.py`:
   - Pydantic `TickLog(BaseModel)`:
     - `tick_id: str` (= run_id of the orchestrator tick)
     - `ran_at: datetime`
     - `actions: list[str]`
   - `def write_tick(root: Path, tick: TickLog) -> Path | None`:
     - Returns `None` and writes nothing if `tick.actions == []`
     - Otherwise writes `.i2e/logs/<tick_id>-tick.yaml` (atomic, immutable — refuse to overwrite)
   - `def latest_tick_for(root: Path, capability: str, item_id: str | None = None) -> TickLog | None`:
     - Walks `.i2e/logs/*-tick.yaml` newest first, returns the first that mentions the capability (and item_id if given) in any action string
   - `def changes_since(root: Path, capability: str, item_id: str, n: int = 3) -> list[tuple[str, str]]`:
     - Returns last `n` `(run_id, change_description)` pairs from tick logs for that item — used by `adapt.escalate` to fill `attempts`
2. Action strings follow a stable grammar so they're greppable:
   - `applied_resolution: <cap> / <item>`
   - `ran_develop: <cap> (intent v<a> -> v<b>)`
   - `ran_evidence: <cap> (<summary>)`
   - `ran_adapt: <cap> (retries=N, escalations=M)`
3. The orchestrator (epic 07) is the only writer; adapt + evidence record their summaries via the orchestrator

## Acceptance Criteria

- [x] Empty-actions tick: `write_tick` returns `None`, no file written
- [x] Non-empty tick: file appears at `.i2e/logs/<tick_id>-tick.yaml`, immutable
- [x] `latest_tick_for("shorten-url")` returns the most recent tick mentioning that cap
- [x] `changes_since` returns at most `n` entries (or fewer if history is short)

## Implementation Notes

- `src/i2e_core/tick_log.py` ships `TickLog` (Pydantic v2, `extra="forbid"`),
  `write_tick`, `latest_tick_for`, and `changes_since`.
- `latest_tick_for` walks `.i2e/logs/*-tick.yaml` newest-first by mtime
  (deterministic across filesystems) and substring-matches the action lines.
- `changes_since` extracts a clean "change description" by stripping the
  leading `<label>:` token and the `<cap>` / `<item>` tokens (whole-word
  regex). When no matching tick is found for a run, the escalation flow
  falls back to the literal placeholder `"(no tick log)"`.
- Corrupt or stale tick-log files are silently skipped — never fatal.
