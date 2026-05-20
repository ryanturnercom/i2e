---
capability: shorten-url
created: 2026-05-19
updated: 2026-05-19
version: 1
status: active
watcher: '@platform-team'
---

# Shorten a URL

A user turns a long URL into a short one and is redirected.

## Evidence of success

- id: code-generated
  type: case
  provider: pytest
  query: tests/test_shorten.py::test_returns_7_char_code
  expect: passes
  effort: medium

- id: redirect-latency-p95
  type: target
  provider: datadog
  query: redirect_latency{quantile=0.95}
  window: 5m
  expect: <50ms
  effort: medium

- id: brand-feel
  type: target
  provider: human
  query: |
    Open the shortener and shorten 3 different URLs.
    Does the experience feel trustworthy and snappy?
  expect: yes
  effort: lazy

## Constraints

- id: no-open-redirect
  provider: pytest
  query: tests/adversarial/test_open_redirect_blocked.py
  expect: passes
  effort: high

- id: pii-not-logged
  provider: sentry
  query: events:contains("http") in:logs
  expect: 0
  effort: high
