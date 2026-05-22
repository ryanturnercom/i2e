---
capability: watcher-notifications
created: '2026-05-20'
updated: '2026-05-21'
version: 1
status: retired
watcher: '@me'
depends_on:
- parallel-agent-visibility
touches:
- src/watcher_notifications/**
- tests/test_watcher_notifications.py
spec: i2e-web-improvements
spec_section: '6'
---

A notifications surface that calls out failure states, items pending a
watcher's input, and targets that need human intervention or feedback.
The aim is for the watcher to land on the page and immediately see
"what needs me?" — not have to hunt for it.

  - We need a notifications piece which denotes failure and/or pending
    things by watcher. Also any targets that need human intervention /
    feedback.

## Evidence of success

- id: watcher-notifications-implemented
  type: case
  provider: pytest
  query: tests/test_watcher_notifications.py::test_implemented
  expect: passes
  effort: medium

## Constraints
