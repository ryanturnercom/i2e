---
capability: console-foundation
created: '2026-05-21'
updated: '2026-05-22'
version: 1
status: shipped
watcher: '@ryan'
touches:
- src/i2e_core/serve.py
- src/i2e_core/console/**
- src/i2e_core/report/last_tick.py
- src/i2e_core/report/templates/last_tick.html.j2
- tests/console/**
- tests/report/test_last_tick.py
spec: i2e-console
spec_section: '1'
---

The shell + dashboard slice of the console rebuild. Lays in the HTMX +
Jinja2 chrome, the sidebar, the topbar, the SSE backbone, and the
cockpit dashboard. Shrinks the static `report.html` artifact to a
last-tick summary so the console becomes the canonical rich UI.

This epic introduces **no console write endpoints**. `i2e-serve` keeps
its current write set (only `.i2e/.serve.url`).

Scope:
- HTMX shell: base template, topbar, sidebar, toast container, footer.
- Sidebar: top nav (Dashboard / Specs / Evidence / Pending / Workers /
  Logs — Specs and Evidence are placeholder pages in this epic) plus a
  filterable Intents list (active / drafts / shipped / retired / all +
  search + sort + grouped-by-status).
- Dashboard view (cockpit layout only): Needs You strip, Shippability
  strip, Workers strip, Capability cards grouped by status, Recent ticks.
- TopBar: eyebrow + title + live pulse counters + UTC clock.
- SSE live-updates with granular kinds (intent / pending / worker /
  tick / job).
- `report.html` shrinks to a last-tick summary rendered by `i2e-report`.

Files: `src/i2e_core/serve.py` (routes the new console), new
`src/i2e_core/console/` package (app, views, sse, prefs, static,
templates), and `src/i2e_core/report/last_tick.py` replacing the
current full-state renderer.

## Evidence of success

- id: dashboard-renders
  type: case
  provider: pytest
  query: tests/console/test_routes.py::test_dashboard_renders
  expect: passes
  effort: medium

- id: sidebar-grouped-filter
  type: case
  provider: pytest
  query: tests/console/test_sidebar.py::test_grouped_filter
  expect: passes
  effort: medium

- id: sse-typed-change-events
  type: case
  provider: pytest
  query: tests/console/test_sse.py::test_typed_change_events
  expect: passes
  effort: medium

- id: last-tick-empty-state
  type: case
  provider: pytest
  query: tests/console/test_last_tick.py::test_renders_when_no_ticks
  expect: passes
  effort: medium

- id: last-tick-summary-renders
  type: case
  provider: pytest
  query: tests/console/test_last_tick.py::test_renders_summary_of_latest
  expect: passes
  effort: medium

- id: dashboard-strips-and-recent-ticks
  type: target
  provider: human
  query: Open the console after running /i2e — does the dashboard show all three strips (Needs You, Shippability, Workers) populated and the Recent ticks list?
  expect: yes — all three strips visible with data, recent ticks list shows at least one entry
  effort: low

## Constraints

- id: serve-binds-localhost-only
  provider: pytest
  query: tests/console/test_security.py::test_binds_127_0_0_1_only
  expect: passes
  effort: medium
