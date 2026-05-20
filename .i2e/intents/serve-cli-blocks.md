---
capability: serve-cli-blocks
created: '2026-05-20'
updated: '2026-05-20'
version: 1
status: active
watcher: '@ryan'
---

# Serve CLI blocks until shutdown

`python -m i2e_core.serve start` must keep the parent process alive while the
HTTP server runs, so backgrounding it from a shell (or harness) yields a
reachable URL after the launching call returns. Today the CLI calls
`start_server()` (which spawns a *daemon* thread) and then returns 0 — the
process exits, the daemon thread dies with it, and `.i2e/.serve.url` is left
pointing at a dead port.

Fix: have the `start` subcommand block (e.g. `threading.Event().wait()` or
`thread.join()`) until SIGINT or a `/shutdown` POST, then ensure
`.serve.url` is removed during the exit path. `stop` continues to work
unchanged (it POSTs to `/shutdown`).

## Evidence of success

- id: blocking-survives-launch
  type: case
  provider: pytest
  query: tests/test_serve_cli.py::test_start_keeps_serving_after_launch_returns
  expect: passes
  effort: medium

- id: stop-shuts-down-cleanly
  type: case
  provider: pytest
  query: tests/test_serve_cli.py::test_stop_terminates_blocking_start
  expect: passes
  effort: medium

## Constraints

- id: no-stale-url-after-shutdown
  provider: pytest
  query: tests/test_serve_cli.py::test_no_stale_serve_url_after_clean_shutdown
  expect: passes
  effort: low
