---
capability: idea-shaped-layout
created: '2026-05-20'
updated: '2026-05-21'
version: 1
status: retired
watcher: '@me'
depends_on:
- live-in-flight-status-panel
touches:
- src/idea_shaped_layout/**
- tests/test_idea_shaped_layout.py
spec: i2e-web-improvements
spec_section: '4'
---

Restructure the report so the Intent → Develop → Evidence → Adapt loop
is the dominant visual frame. The reader should be able to point at a
region of the page and name which IDEA stage it represents. Also: a
general cleanup pass on spacing, hierarchy, and chrome.

  - Layout the process from the IDEA perspective as much as possible —
    I want the flow to be very obvious.
  - Clean up.

## Evidence of success

- id: idea-shaped-layout-implemented
  type: case
  provider: pytest
  query: tests/test_idea_shaped_layout.py::test_implemented
  expect: passes
  effort: medium

## Constraints
