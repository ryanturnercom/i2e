---
capability: light-and-dark-mode
created: '2026-05-21'
updated: '2026-05-22'
version: 4
status: active
watcher: '@me'
depends_on:
- console-foundation
touches:
- src/i2e_core/console/**
- src/light_and_dark_mode/**
- tests/console/**
- tests/test_light_and_dark_mode.py
spec: i2e-console
spec_section: '2'
---

In the tweak settings I want to see light and dark mode and I want it to be remembered on refresh.



#### Acceptance evidence (to be wired up via `i2e-intent`)

Cases (pytest):
- `tests/console/test_routes.py::test_dashboard_renders`
- `tests/console/test_sidebar.py::test_grouped_filter`
- `tests/console/test_sse.py::test_typed_change_events`
- `tests/console/test_last_tick.py::test_renders_when_no_ticks`
- `tests/console/test_last_tick.py::test_renders_summary_of_latest`

Targets (human):
- "Open the console after running `/i2e` — does the dashboard show all
  three strips populated and the recent ticks list?"

Constraints (pytest):
- `tests/console/test_security.py::test_binds_127_0_0_1_only`

Estimate: ~1 week.

## Evidence of success

- id: light-and-dark-mode-implemented
  type: case
  provider: pytest
  query: tests/console/test_tweaks.py::test_theme_axis_present_and_persists
  expect: passes
  effort: medium

- id: theme-visible-in-tweak-menu
  type: target
  provider: human
  query: Open the console and click the gear icon to open the Tweaks panel. Confirm a Light/Dark mode (theme) control is listed there alongside Density, Sidebar, etc., switch it to Dark, then reload the page. Is the theme control present and does the Dark choice survive the refresh?
  expect: yes — the Tweaks panel shows a Light/Dark theme control and the chosen mode survives a page refresh
  effort: low
  url: http://127.0.0.1:4230/

- id: theme-axis-in-panel
  type: case
  provider: pytest
  query: tests/console/test_tweaks.py::test_theme_axis_in_panel
  expect: passes
  effort: medium

## Constraints
