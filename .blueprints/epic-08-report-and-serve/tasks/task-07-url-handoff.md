# Task: .serve.url handoff (file:// vs http://)

**Status:** [ ] Pending

**Dependencies:** task-06-localhost-sse

## Context

Spec §8 — agents share deep links. If `.serve.url` exists, prefer `http://localhost/...#fragment`; otherwise use `file://.../report.html#fragment`. The fragment scheme is identical.

## Needed from User

None.

## Instructions

1. Add `src/i2e_core/report/links.py`:
   - `def deep_link(root: Path, fragment: str) -> str`:
     - If `.i2e/.serve.url` exists: `<url><fragment>`
     - Else: `file://<absolute path to .i2e/report.html><fragment>`
     - `fragment` includes the leading `#`
   - Conveniences:
     - `link_capability(root, slug) -> str`
     - `link_item(root, slug, item_id) -> str`
     - `link_pending(root, filename) -> str`
     - `link_tick(root, tick_id) -> str`
2. Wire `orchestrator.tick` to include a `deep_link(...)` for the last action in its returned `TickResult.report_link` field — useful for chat handoffs
3. Tests:
   - With `.serve.url` present → HTTP URL
   - Without → file:// URL with absolute path

## Acceptance Criteria

- [ ] `link_capability` returns the right form in both modes
- [ ] file:// URLs are absolute (Windows-safe: `file:///C:/...`)
- [ ] `TickResult.report_link` is populated after non-empty ticks
