---
capability: serve-autoreload
created: '2026-05-22'
updated: '2026-05-22'
version: 2
status: active
watcher: '@ryan'
depends_on:
- console-foundation
touches:
- src/i2e_core/serve.py
- src/i2e_core/config.py
- src/i2e_core/console/app.py
- src/i2e_core/console/static/console.js
- tests/serve/**
- tests/test_config.py
---

# Auto-reload the console server on code changes

When `serve.autoreload` is enabled, the running `i2e serve` server watches
its own `i2e_core` package for `.py` changes and re-execs itself in place
(same PID, same terminal) so an operator iterating on console code never
has to restart by hand. The browser reloads itself once the fresh server
is back.

Behaviour:
- New config key `serve.autoreload` (bool, default `false`). Off by
  default — an installed, non-editable i2e_core never changes, so the
  watcher only earns its keep when dogfooding i2e itself.
- With it on, `start_server` schedules a second watch (on the existing
  observer) over the `i2e_core` package directory. A debounced `.py`
  change triggers the existing `_restart` path (`server.shutdown()` +
  `os.execv`).
- Static assets (`/static/*`) are served `Cache-Control: no-store`
  instead of `max-age=3600`, so a CSS/JS edit shows on a plain browser
  refresh with no restart at all.
- `console.js` reloads the page once the SSE channel reconnects after
  the server went away — so a code-change restart is fully hands-free.

Largely supersedes the `serve-restart-button` capability for day-to-day
iteration: the restart becomes automatic instead of a manual click.

## Evidence of success

- id: autoreload-config-defaults-off
  type: case
  provider: pytest
  query: tests/test_config.py::test_autoreload_defaults_off
  expect: passes
  effort: low

- id: autoreload-watches-code-dir
  type: case
  provider: pytest
  query: tests/serve/test_autoreload.py::test_autoreload_watches_code_dir
  expect: passes
  effort: medium

- id: code-change-triggers-reexec
  type: case
  provider: pytest
  query: tests/serve/test_autoreload.py::test_code_change_triggers_reexec
  expect: passes
  effort: medium

- id: static-assets-no-store
  type: case
  provider: pytest
  query: tests/serve/test_autoreload.py::test_static_assets_served_no_store
  expect: passes
  effort: low

- id: autoreload-end-to-end
  type: target
  provider: human
  query: With serve.autoreload enabled in .i2e/config.yaml, start the server and edit a console source file (e.g. add a comment to shell.py). Does the server restart on its own and the page reload, without you touching the terminal?
  expect: yes — the server re-execs in the same terminal within a second or two of the save and the browser reloads itself
  effort: low

## Constraints
