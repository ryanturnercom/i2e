---
capability: shorten-url
created: 2026-05-19
updated: 2026-05-19
version: 1
status: active
watcher: '@me'
---

# Shorten a URL

A user submits a long URL and receives a short code. Visiting the short code redirects to the original URL. Unsafe URL schemes are refused.

## Evidence of success

- id: code-generated
  type: case
  provider: pytest
  query: tests/test_shorten.py::test_returns_7_char_code
  expect: passes
  effort: medium

- id: round-trip-resolves
  type: case
  provider: pytest
  query: tests/test_shorten.py::test_round_trip
  expect: passes
  effort: medium

- id: codes-unique
  type: case
  provider: pytest
  query: tests/test_shorten.py::test_unique_codes_under_load
  expect: passes
  effort: medium

## Constraints

- id: no-open-redirect
  provider: pytest
  query: tests/adversarial/test_open_redirect_blocked.py
  expect: passes
  effort: high
