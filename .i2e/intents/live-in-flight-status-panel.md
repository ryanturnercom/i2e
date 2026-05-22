---
capability: live-in-flight-status-panel
created: '2026-05-20'
updated: '2026-05-21'
version: 1
status: retired
watcher: '@me'
depends_on:
- capability-case-details-on-click
touches:
- src/live_in_flight_status_panel/**
- tests/test_live_in_flight_status_panel.py
spec: i2e-web-improvements
spec_section: '3'
---

Surface which specs and intents are being worked on right now and their
current real-time status. This pulls from `current.yaml`, any pending
files, and (once swarm worktrees land) the active claim records under
`.i2e/worktrees/`.

  - Be able to view which specs and intents are being worked in and
    their current real-time status.

## Evidence of success

- id: live-in-flight-status-panel-implemented
  type: case
  provider: pytest
  query: tests/test_live_in_flight_status_panel.py::test_implemented
  expect: passes
  effort: medium

## Constraints
