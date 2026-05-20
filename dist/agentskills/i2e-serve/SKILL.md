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
1. Preflight: if `.i2e/.serve.url` already exists, either reuse it (curl it — HTTP 200 means a live server) or remove the stale file before starting. Don't print a URL for a dead server.
2. Start `i2e_core.serve.start_server(root)` (returns the URL) — see "How to start (detached)" below for the correct invocation.
3. Verify with a quick `curl -sS -o /dev/null -w "%{http_code}" <url>` — expect `200`.
4. Return to the user with: "Serving at <url> — open <url>#cap/<slug> to land on that capability"
5. The server runs detached until the user kills it (`i2e-serve stop`)

## How to start (detached)

**Do NOT** use `python -m i2e_core.serve start` for detached operation. The CLI calls `start_server()` (which spawns a daemon thread) and then returns — the parent process exits immediately, which kills the daemon thread. The `.serve.url` file is left behind pointing at a dead port.

Run an inline wrapper that blocks the main thread instead, backgrounded by the harness:

```powershell
.venv\Scripts\python.exe -c "from pathlib import Path; from i2e_core.serve import start_server; import threading; print('URL:', start_server(Path('.')), flush=True); threading.Event().wait()"
```

Launch it with `Bash`'s `run_in_background: true` so it stays alive. Read the first line of the output file to capture the URL, then verify with curl before reporting to the user.

(Filing an intent to make the CLI `start` block on its own would let step 2 collapse back to a one-liner. Until then, the inline wrapper is the right form.)

## Stop
`python -m i2e_core.serve stop` — reads `.serve.url`, sends shutdown signal, removes the file. If you started the server via the inline wrapper above, `stop` works the same way (it posts to `/shutdown` over HTTP).
