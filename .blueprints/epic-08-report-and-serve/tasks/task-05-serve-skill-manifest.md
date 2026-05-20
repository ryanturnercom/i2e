# Task: SKILL.md manifest for i2e-serve

**Status:** [ ] Pending

**Dependencies:** None

## Context

`i2e-serve` is the optional live-view companion to `i2e-report`. It's user-invoked (not auto-invoked) and must be safe by default (loopback only).

## Needed from User

None.

## Instructions

1. Create `.claude/skills/i2e-serve/SKILL.md`:

```markdown
---
name: i2e-serve
description: Optional. Start a localhost HTTP server with SSE updates on .i2e/ changes. Bound to 127.0.0.1 only. Writes .i2e/.serve.url when up; deletes it on shutdown.
license: Apache-2.0
metadata:
  tier: loop
  version: "0.1.0"
  optional: true
---

# i2e-serve

## When to use
- The user is actively iterating and wants live updates without manual reloads
- A teammate wants to point at `.serve.url` in a chat

## Boundaries
- Bind: 127.0.0.1 only (refuse to bind 0.0.0.0)
- No auth — loopback only. Document this in the README.
- Ephemeral port; URL written to `.i2e/.serve.url`

## Workflow
1. Start `i2e_core.serve.start_server(root)` (returns the URL)
2. Returns to the user with: "Serving at <url> — open <url>#cap/<slug> to land on that capability"
3. The server runs detached until the user kills it (`i2e-serve stop`)

## Stop
`python -m i2e_core.serve stop` — reads `.serve.url`, sends shutdown signal, removes the file
```

2. Stub `src/i2e_core/serve.py` with `start_server(root)`, `stop_server(root)`

## Acceptance Criteria

- [ ] SKILL.md exists with `metadata.optional: true`
- [ ] `i2e_core.serve.start_server` and `stop_server` are importable
- [ ] SKILL.md documents the 127.0.0.1 bind requirement and no-auth caveat
