# Task: Tests for renderer + server lifecycle

**Status:** [ ] Pending

**Dependencies:** task-03-view-model, task-04-auto-invocation, task-06-localhost-sse, task-07-url-handoff

## Context

Tests covering report determinism, the orchestrator hook, server lifecycle (start/stop), and link generation.

## Needed from User

None.

## Instructions

1. `tests/report/test_view_model.py`:
   - Empty project → empty view model
   - One capability with 3 items, mixed verdicts → view model has 3 items with correct max_attempts
   - `shippable` true only when all green
2. `tests/report/test_render.py`:
   - HTML contains all required deep-link ids
   - Re-render with unchanged state produces identical bytes
3. `tests/report/test_links.py`:
   - With `.serve.url`: HTTP-prefixed
   - Without: `file://` absolute (Windows path-encoded correctly)
4. `tests/serve/test_lifecycle.py`:
   - Start, hit `/`, get HTML, hit `/events`, modify a `.i2e/` file, see an SSE event, stop, `.serve.url` removed
   - Refuse non-loopback host
5. `tests/orchestrator/test_report_invocation.py` already covers auto-invocation (from task-04)

## Acceptance Criteria

- [ ] All tests pass via `pytest tests/report tests/serve -q`
- [ ] Server lifecycle test cleanly shuts down (no leaked threads)
- [ ] Coverage of `report/` + `serve.py` is >80% (server tests can be flaky; document that >80% is the bar)
