---
capability: serve-no-self-refresh-loop
created: '2026-05-20'
updated: '2026-05-21'
version: 1
status: shipped
watcher: '@ryan'
touches:
- src/i2e_core/serve.py
- tests/test_serve_no_self_refresh.py
---

# i2e-serve must not self-trigger refreshes

The SSE live-reload path currently feeds itself. Each `GET /` calls
`render(root)` in `_serve_index`, which atomically writes `.i2e/report.html`
(plus a sibling `.tmp` from `io_utils.atomic_write`). The watchdog observer
started in `start_server()` watches `.i2e/` recursively, and
`_WatchdogHandler._emit` (serve.py:111) only filters out files named
`.serve.url` — `report.html` and `report.html.tmp` pass through. After the
200ms debounce the broker fires a `change` SSE event. The browser's
`EventSource` listener calls `location.reload()`, which issues another
`GET /`, which re-renders, ... Steady-state refresh on localhost is ~2–4 Hz.

Fix: ignore the server's own self-written outputs in `_WatchdogHandler._emit`,
the same way `.serve.url` is already filtered. The simplest form:

```python
_SELF_WRITTEN = {".serve.url", "report.html", "report.html.tmp"}
if p.name in _SELF_WRITTEN:
    return
```

An equally valid alternative is to narrow the watcher scope: schedule the
observer on `intents/`, `evidence/`, `pending/`, and `logs/` subdirs only,
and skip root-level files in `.i2e/`. Either approach is acceptable as long
as the evidence below passes.

Out of scope: changing the 200ms debounce window or the `ready`-on-connect
behavior of `/events`.

## Evidence of success

- id: single-get-emits-no-change
  type: case
  provider: pytest
  query: tests/test_serve_no_self_refresh.py::test_single_get_root_emits_no_change_event
  expect: passes
  effort: medium

- id: intent-write-emits-change
  type: case
  provider: pytest
  query: tests/test_serve_no_self_refresh.py::test_intent_file_write_emits_change_event
  expect: passes
  effort: medium

- id: render-write-emits-no-change
  type: case
  provider: pytest
  query: tests/test_serve_no_self_refresh.py::test_render_writing_report_html_emits_no_change_event
  expect: passes
  effort: medium

## Constraints

- id: ready-and-debounce-unchanged
  provider: pytest
  query: tests/test_serve_no_self_refresh.py::test_ready_event_and_debounce_window_unchanged
  expect: passes
  effort: low
