---
capability: remove-dashboard-tweak
created: '2026-05-22'
updated: '2026-05-22'
version: 1
status: active
watcher: '@ryan'
depends_on:
- console-foundation
touches:
- src/i2e_core/console/shell.py
- src/i2e_core/console/prefs.py
- src/i2e_core/console/views/dashboard.py
- tests/console/**
---

# Remove the Dashboard tweak axis

The Tweaks panel exposes a "Dashboard" selector (cockpit / IDEA arc /
inbox). It is confusing: the selector lives in the global panel shown
on every page, but it only affects the Dashboard route, and the three
layouts differ only in subtle block ordering — so toggling it usually
looks like it does nothing.

Remove it cleanly:
- Drop the `dashboard` axis from the Tweaks panel (`_TWEAK_AXES` in
  `shell.py`).
- Drop the `dashboard` key from the `i2e_console_prefs` cookie schema
  (`DEFAULT_PREFS` in `prefs.py`); an old cookie still carrying a
  `dashboard` value is silently ignored.
- The Dashboard view always renders the cockpit layout. The `arc` and
  `inbox` branches in `dashboard.py` become unreachable once the
  selector is gone, so delete them rather than leave dead code.

Cockpit stays as the single, canonical Dashboard layout.

## Evidence of success

- id: dashboard-axis-absent
  type: case
  provider: pytest
  query: tests/console/test_remove_dashboard_tweak.py::test_tweaks_panel_has_no_dashboard_axis
  expect: passes
  effort: medium

- id: dashboard-pref-key-removed
  type: case
  provider: pytest
  query: tests/console/test_remove_dashboard_tweak.py::test_dashboard_pref_key_removed
  expect: passes
  effort: medium

## Constraints
