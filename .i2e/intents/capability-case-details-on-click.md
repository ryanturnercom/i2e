---
capability: capability-case-details-on-click
created: '2026-05-20'
updated: '2026-05-21'
version: 1
status: retired
watcher: '@me'
depends_on:
- intent-status-controls-in-the-report
touches:
- src/capability_case_details_on_click/**
- tests/test_capability_case_details_on_click.py
spec: i2e-web-improvements
spec_section: '2'
---

Clicking a capability expands it to show the underlying evidence —
cases, constraints, and their latest verdicts — so a watcher can drill
from the high-level shippable signal down to the failing query without
leaving the page.

  - Ability to click on a capability and see the case(s).

## Evidence of success

- id: capability-case-details-on-click-implemented
  type: case
  provider: pytest
  query: tests/test_capability_case_details_on_click.py::test_implemented
  expect: passes
  effort: medium

## Constraints
