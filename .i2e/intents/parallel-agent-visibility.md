---
capability: parallel-agent-visibility
created: '2026-05-20'
updated: '2026-05-21'
version: 1
status: retired
watcher: '@me'
depends_on:
- idea-shaped-layout
touches:
- src/parallel_agent_visibility/**
- tests/test_parallel_agent_visibility.py
spec: i2e-web-improvements
spec_section: '5'
---

Make it explicit what is being worked on and how many things are running
simultaneously across agents. Tie into the swarm worktree claim records
so each running develop/evidence/adapt step is visible with its agent
id and progress text.

  - Make it clear what is being worked on and how many simultaneously
    (different agents).

## Evidence of success

- id: parallel-agent-visibility-implemented
  type: case
  provider: pytest
  query: tests/test_parallel_agent_visibility.py::test_implemented
  expect: passes
  effort: medium

## Constraints
