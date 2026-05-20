# Task: i2e-provider-human skill + pending writer

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-01-provider-contract, task-02-provider-discovery

## Context

Spec Appendix A defines `i2e-provider-human` as the canonical async provider. On first invocation it writes a pending file and returns `awaiting_human`. The orchestrator picks the resolution up on a later tick (epic 06 + 07 wire that path).

This task ships the provider and the pending-file writer. The writer is reused by other async providers (`survey`, `interview`) in epic 09.

## Needed from User

None.

## Instructions

1. Create `src/i2e_core/pending.py`:
   - Pydantic model `PendingFile`:
     - `status: Literal["open","resolved"] = "open"`
     - `kind: Literal["escalation","human_evaluation"]`
     - `capability: str`
     - `item_id: str`
     - `asked_at: datetime | None = None`
     - `escalated_at: datetime | None = None`
     - `reason: str | None = None`
     - `expect: str | None = None`
     - `observed: str | None = None`
     - `attempts: list[dict] = []`
     - `ask: str`
     - `verdict_options: list[str] | None = None`
     - `resolution: str | None = None`
   - `def pending_filename(capability: str, item_id: str, when: datetime | None = None) -> str` — `YYYY-MM-DD-<capability>-<item-id>.yaml`
   - `def write_pending(root: Path, pf: PendingFile) -> Path` — atomic write to `.i2e/pending/<filename>`; raises `FileExistsError` if it already exists (one open pending per item)
   - `def read_pending(path: Path) -> PendingFile`
   - `def list_open_pending(root: Path) -> list[Path]`
   - `def list_resolved_pending(root: Path) -> list[Path]`
   - `def archive_pending(root: Path, path: Path) -> Path` — moves to `.i2e/logs/<basename>` atomically (`os.replace`)
2. Create the skill folder `.claude/skills/i2e-provider-human/` with:

**`SKILL.md`**
```markdown
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
```

**`provider.py`**
```python
from __future__ import annotations
from datetime import datetime, timezone
from i2e_core.provider import AsyncResult, ProviderContext
from i2e_core.pending import PendingFile, pending_filename, write_pending

class HumanProvider:
    name = "human"

    def invoke(self, item, ctx: ProviderContext) -> AsyncResult:
        now = datetime.now(timezone.utc)
        pf = PendingFile(
            kind="human_evaluation",
            capability=ctx.capability,
            item_id=item.id,
            asked_at=now,
            ask=item.query,
            verdict_options=["yes", "no", "partial"],
        )
        path = write_pending(ctx.root, pf)
        return AsyncResult(verdict="awaiting_human", pending=path.name)

provider = HumanProvider()
```

3. Tests:
   - Round-trip a `PendingFile` through write/read
   - Calling `HumanProvider().invoke(...)` writes a file and returns its basename
   - A second call for the same item raises `FileExistsError` (one open pending per item)
   - `archive_pending` moves the file to `.i2e/logs/` and deletes the original

## Acceptance Criteria

- [x] `.claude/skills/i2e-provider-human/SKILL.md` exists and parses
- [x] `load_provider("human")` returns a `Provider` whose `name == "human"`
- [x] First invocation writes a file matching `pending_filename(cap, item.id)` and returns `verdict="awaiting_human"`
- [x] Second invocation for an item with an open pending raises `FileExistsError`
- [x] `archive_pending` is atomic (target file exists, source file gone, or both unchanged on error)

## Implementation Notes

- `PendingFile` is Pydantic v2 with `extra="forbid"` to keep the on-disk shape stable; datetimes are serialized via `model_dump(mode="json")` so they round-trip cleanly as ISO 8601 strings.
- `write_pending` uses the existing `atomic_write` helper (`*.tmp` + `os.replace`). `archive_pending` uses `os.replace` directly, which is atomic on Windows and POSIX.
- `list_open_pending` / `list_resolved_pending` skip unparseable YAML files (operator can clean up by hand) rather than crashing the orchestrator.
- The human provider also stamps `item.expect` into the pending file so the eventual resolver sees what was originally expected.
