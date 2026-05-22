---
capability: rocksalt-logo-font
created: '2026-05-20'
updated: '2026-05-21'
version: 1
status: retired
watcher: '@me'
depends_on:
- watcher-notifications
touches:
- src/rocksalt_logo_font/**
- tests/test_rocksalt_logo_font.py
spec: i2e-web-improvements
spec_section: '7'
---

Apply the Google Font "Rocksalt" to the i2e logo / wordmark in the
report header so the brand matches ryanturner.com.

  - The google font rocksalt can be used for the i2e logo as it's the
    same font as ryanturner.com logo would be.

## Evidence of success

- id: rocksalt-logo-font-implemented
  type: case
  provider: pytest
  query: tests/test_rocksalt_logo_font.py::test_implemented
  expect: passes
  effort: medium

## Constraints
