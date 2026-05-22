---
capability: intent-status-controls-in-the-report
created: '2026-05-20'
updated: '2026-05-21'
version: 1
status: retired
watcher: '@me'
touches:
- src/intent_status_controls_in_the_report/**
- tests/test_intent_status_controls_in_the_report.py
spec: i2e-web-improvements
spec_section: '1'
---

Promote and demote intents directly from the experience. Each capability
card surfaces controls to flip its status (`draft` → `active` →
`retired`) without hand-editing frontmatter. The action writes to the
intent file on disk so the next tick sees the new state.

  - Be able to change the status of an intent from the experience.
    Promote / Demote.

## Evidence of success

- id: intent-status-controls-in-the-report-implemented
  type: case
  provider: pytest
  query: tests/test_intent_status_controls_in_the_report.py::test_implemented
  expect: passes
  effort: medium

## Constraints
