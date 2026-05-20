# Epic: i2e-adapt Skill

**Status:** [✓] Completed
**Source spec:** .documentation/I2E_simplified.md
**Started:** 2026-05-19
**Completed:** 2026-05-19

## Context

`i2e-adapt` is the loop's brain. It reads `current.yaml`, finds items that are `fail`, `unmet`, or `trending`, and decides whether to attempt another auto-improvement cycle or escalate to a human.

Budget rules (spec §2.3):
- Each item has an `effort` tier (`lazy` | `low` | `medium` | `high`)
- Tier → `max_attempts` map lives in `.i2e/config.yaml`
- `attempts_used >= max_attempts` ⇒ write a `pending/` file with `kind: escalation`

On the next tick, `i2e` applies any `status: resolved` pending file back to the intent (loosen, retry, retire, accept) and archives the pending file to `logs/`.

## Implementation Overview

- Ship a SKILL.md at `~/.claude/skills/i2e-adapt/SKILL.md`
- A workflow that:
  1. Reads the latest `current.yaml` for a capability
  2. For each non-passing item: checks `attempts_used` against tier budget
  3. Budget remaining → propose a code/intent change, increment `attempts_used`, signal "run develop+evidence again"
  4. Budget exhausted → write `.i2e/pending/<date>-<cap>-<id>.yaml` with `kind: escalation` and an `ask:` block
- A resolution applier (called from the orchestrator's preflight) that:
  1. Finds pending files with `status: resolved`
  2. Translates each resolution choice (loosen / new approach / retire / accept) into an intent file edit
  3. Moves the pending file to `.i2e/logs/`
- A tick-log writer that appends to `.i2e/logs/<tick-id>-tick.yaml`

## Tasks

- [x] [task-01: SKILL.md manifest for i2e-adapt](tasks/task-01-skill-manifest.md)
- [x] [task-02: Budget tracker](tasks/task-02-budget-tracker.md)
- [x] [task-03: Escalation pending-file generator](tasks/task-03-pending-generator.md)
- [x] [task-04: Resolution applier](tasks/task-04-resolution-applier.md)
- [x] [task-05: Tick-log writer](tasks/task-05-tick-log.md)
- [x] [task-06: Tests for budgets, escalation, resolution](tasks/task-06-tests.md)

## Outcome

**Shipped:**
- `.claude/skills/i2e-adapt/SKILL.md` — manifest with explicit intent-file
  carve-out documenting `apply_resolutions` as the single gated exception.
- `src/i2e_core/adapt.py` — `plan`, `escalate`, `has_open_escalation`,
  `apply_resolutions`; Pydantic v2 models `AdaptPlan`, `ItemBudget`,
  `ResolutionApplied`. Resolution parser accepts 1-4, `1.`, `1)`,
  `option 1`, and the keywords loosen/new/retire/accept.
- `src/i2e_core/tick_log.py` — `TickLog`, `write_tick` (atomic,
  immutable, empty-actions-no-file), `latest_tick_for`, `changes_since`.
- `tests/adapt/` — 37 tests across 4 files + a shared conftest.

**Gate:**
- `.venv\Scripts\python.exe -m pytest -q` → **220 passed**
  (183 existing + 37 new).
- Coverage: 94% overall; `adapt.py` 85%, `tick_log.py` 95% (both ≥ 85%).

**Notes:**
- Option 1 (loosen) requires `new expect: <value>` — refuses silent intent
  edits.
- Option 2 (new approach) stores the approach text under
  `current.items[id].raw.new_approach` so the next develop pass can read
  it, and resets `attempts_used` to 0. Intent untouched.
- Option 4 (accept) writes only to `current.yaml`; intent untouched.
- `apply_resolutions` is best-effort batch: per-file errors leave the
  pending file in place, never raise.
- The "intent-file carve-out" is documented in both the SKILL.md
  Boundaries section and the `apply_resolutions` docstring; the write
  goes through `intent.write_intent` for atomicity.
