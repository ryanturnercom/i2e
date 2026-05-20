# Epic: i2e-report Renderer + i2e-serve Live Server

**Status:** [x] Complete
**Source spec:** .documentation/I2E_simplified.md
**Started:** 2026-05-19

## Context

Two skills, one renderer, same templates (spec §8):

- `i2e-report` — deterministic Python; renders `.i2e/report.html` from current state. Auto-invoked by the orchestrator after any state-changing tick. **Zero LLM tokens.**
- `i2e-serve` — optional; starts a localhost HTTP server (127.0.0.1 only) with SSE pushes on `.i2e/` mtime changes

Deep-link fragments (`#cap/...`, `#item/...`, `#pending/...`, `#tick/...`) are the same scheme in both modes. The agent picks `http://localhost:<port>/...` if `.i2e/.serve.url` exists, otherwise `file:///.../report.html#...`.

## Implementation Overview

### Report
- Jinja2 templates under `src/i2e_core/report/templates/`
- View model builder that snapshots: every active capability, its `current.yaml`, every open pending file, last 10 tick logs
- A single entry point `i2e_core.report.render() -> writes .i2e/report.html`
- Ship `~/.claude/skills/i2e-report/SKILL.md` that calls the entry point — pure Python, no LLM

### Serve
- Stdlib `http.server` bound to 127.0.0.1 on an ephemeral port
- `watchdog` watches `.i2e/` recursively; on any change, push an SSE event with the changed path
- Writes `.i2e/.serve.url` on start; removes it on shutdown
- Ship `~/.claude/skills/i2e-serve/SKILL.md` that starts the server detached

## Tasks

- [x] [task-01: SKILL.md manifest for i2e-report](tasks/task-01-report-skill-manifest.md)
- [x] [task-02: HTML template + deep-link fragments](tasks/task-02-html-template.md)
- [x] [task-03: State-to-view-model mapper](tasks/task-03-view-model.md)
- [x] [task-04: Auto-invocation hook from orchestrator](tasks/task-04-auto-invocation.md)
- [x] [task-05: SKILL.md manifest for i2e-serve](tasks/task-05-serve-skill-manifest.md)
- [x] [task-06: Localhost HTTP server + SSE updates](tasks/task-06-localhost-sse.md)
- [x] [task-07: .serve.url handoff (file:// vs http://)](tasks/task-07-url-handoff.md)
- [x] [task-08: Tests for renderer + server lifecycle](tasks/task-08-tests.md)
