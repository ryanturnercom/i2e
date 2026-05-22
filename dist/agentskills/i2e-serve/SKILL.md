---
name: i2e-serve
description: Optional. Reports whether the localhost report server is up and tells the operator how to run it. Advisory only — never starts or stops the server.
license: Apache-2.0
metadata:
  tier: loop
  version: "0.2.0"
  optional: true
---

# i2e-serve

The localhost report server is **operator-owned**. This skill never starts
it, never stops it, and never runs it in the Claude Code background. It only
checks whether the server is up and, if not, tells the operator how to start
it themselves.

Why operator-owned: the operator runs `start.sh` in their own terminal so the
server outlives the Claude Code session and they see its output directly. A
server launched inside the harness dies with the session and gets killed by
later skills — surprising and annoying. Skills stay hands-off.

## When to use
- The user asks for live updates, or where the report is being served
- A teammate wants a URL to point at

## What this skill MUST NOT do
- Do not run `i2e_core.serve start` (foreground or background)
- Do not run `i2e_core.serve stop`, kill, or restart a running server
- Do not run `start.sh` / `stop.sh` / `restart.sh` yourself
- Do not write any file under `.i2e/`

If the user explicitly asks you to start or stop the server, point them at
the scripts below — do not run them for them.

## Workflow
1. **Check whether the server is up.** If `.i2e/.serve.url` exists, read it
   and probe: `curl -sS -o /dev/null -w "%{http_code}" <url>`.
   - `200` → the server is live. Tell the user: "Serving at <url> — open
     `<url>#cap/<slug>` to land on a capability."
   - No file, or curl fails / non-200 → the server is not running (a
     present-but-dead `.serve.url` is just stale). Go to step 2.
2. **Tell the user how to start it themselves.** Give them this exact
   command to paste into their own terminal:

   ```bash
   bash .i2e/start.sh
   ```

   `start.sh` runs in the foreground and blocks — that terminal becomes the
   server, and prints the URL on startup. The operator leaves it running and
   opens the URL in a browser. The static `.i2e/report.html` always works
   without a server.

## The helper scripts (operator-run, never skill-run)
`python -m i2e_core.init` installs three scripts in `.i2e/`:

- `bash .i2e/start.sh` — start the server (foreground; blocks until Ctrl+C)
- `bash .i2e/stop.sh` — stop the running server
- `bash .i2e/restart.sh` — stop, then start

All three are for the **operator** to run. Never run them from a skill.

## Boundaries
- Bind: 127.0.0.1 only — loopback, no auth (documented in the README)
- Port: static `4230` by default; override via `serve.port` in
  `.i2e/config.yaml`
- Writes nothing — purely advisory
