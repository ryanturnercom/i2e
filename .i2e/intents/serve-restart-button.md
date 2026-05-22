---
capability: serve-restart-button
created: '2026-05-22'
updated: '2026-05-22'
version: 1
status: active
watcher: '@ryan'
depends_on:
- console-workers-logs-specs-evidence
touches:
- src/i2e_core/serve.py
- src/i2e_core/console/app.py
- src/i2e_core/console/shell.py
- src/i2e_core/console/static/**
- tests/console/**
---

# Restart button in the Tweaks panel

A **Restart** button in the floating Tweaks panel that restarts the
running console web server, then reloads the page once the fresh
server is back up.

Behaviour:
- The Tweaks panel gains a "Server" section with a **Restart** button,
  below the existing Layout axes.
- Clicking it POSTs to a restart endpoint on `i2e-serve` (a sibling of
  the existing `/shutdown`). The server re-executes itself in place
  via `os.execv` — same PID, same terminal — so the operator's
  foreground `start.sh` process keeps running and picks up code or
  config changes.
- After POSTing, the client waits 10 seconds (enough for the server
  to rebind its static port) and then reloads the current page.
- The restart endpoint keeps the existing 127.0.0.1-only bind — it
  is a server-lifecycle operation, not a new attack surface.

This is a convenience for operators iterating on the console: instead
of switching to the terminal to run `restart.sh`, they restart from
the UI and the page comes back on its own.

## Evidence of success

- id: restart-button-renders
  type: case
  provider: pytest
  query: tests/console/test_restart.py::test_tweaks_panel_has_restart_button
  expect: passes
  effort: medium

- id: restart-endpoint-reexecs
  type: case
  provider: pytest
  query: tests/console/test_restart.py::test_restart_endpoint_triggers_reexec
  expect: passes
  effort: medium

- id: client-reloads-after-delay
  type: case
  provider: pytest
  query: tests/console/test_restart.py::test_restart_button_reloads_after_10s
  expect: passes
  effort: medium

- id: restart-end-to-end
  type: target
  provider: human
  query: Click the Restart button in the Tweaks panel. Does the server restart in place and the page reload itself after about 10 seconds?
  expect: yes — the server re-execs in the same terminal and the page reloads on its own roughly 10s later, showing the fresh server
  effort: low

## Constraints
