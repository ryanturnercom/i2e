---
capability: serve-static-port-and-browser
created: '2026-05-21'
updated: '2026-05-21'
version: 1
status: retired
watcher: '@ryan'
---

# Serve uses a static port and opens the browser

`i2e-serve` historically bound to an ephemeral OS-assigned port, so the URL
changed on every restart. The user wanted a stable, bookmarkable URL with
a config override, and the browser should auto-open when possible.

Behaviour:
- Default port is `4230`, exposed as `serve.port` in `.i2e/config.yaml`.
- `serve.open_browser: true` (default) opens the URL in the default browser
  shortly after the server starts.
- `start_server(root, port=None, open_browser=None)` reads config when args
  are `None`. Pass `port=0` for an ephemeral port (tests).
- CLI: `--port N` and `--no-browser` / `--open-browser` override config.

## Evidence of success

- id: config-defaults-include-serve-section
  type: case
  provider: pytest
  query: tests/test_config.py::test_serve_defaults
  expect: passes
  effort: low

- id: config-override-port-and-browser
  type: case
  provider: pytest
  query: tests/test_config.py::test_serve_partial_override
  expect: passes
  effort: low

- id: static-port-honoured-from-config
  type: case
  provider: pytest
  query: tests/serve/test_static_port.py::test_static_port_from_config_is_used
  expect: passes
  effort: medium

- id: explicit-port-arg-wins-over-config
  type: case
  provider: pytest
  query: tests/serve/test_static_port.py::test_explicit_port_arg_overrides_config
  expect: passes
  effort: medium

- id: browser-open-fires-when-enabled
  type: case
  provider: pytest
  query: tests/serve/test_static_port.py::test_browser_opens_when_enabled
  expect: passes
  effort: medium

- id: browser-open-suppressed-when-disabled
  type: case
  provider: pytest
  query: tests/serve/test_static_port.py::test_browser_does_not_open_when_disabled
  expect: passes
  effort: low

## Constraints

- id: ephemeral-port-still-available
  provider: pytest
  query: tests/serve/test_lifecycle.py::test_start_returns_loopback_url_and_writes_serve_file
  expect: passes
  effort: low
