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
2. **Offer the command, then ask.** Show the user the exact bash command they can paste into their own terminal (so the server outlives the Claude Code session), then use `AskUserQuestion` to ask Y/n whether to run it here in the harness background instead. The default recommendation is "run it yourself" — but honour their choice.

   The command to present (bash, runnable from the project root):

   ```bash
   .venv/Scripts/python.exe -c "from pathlib import Path; from i2e_core.serve import start_server; import threading; print('URL:', start_server(Path('.')), flush=True); threading.Event().wait()"
   ```

   - If user picks **Yes (run it here)**: launch the same command via `Bash` with `run_in_background: true`. Wait for `.i2e/.serve.url` to appear, then jump to step 3.
   - If user picks **No (I'll run it myself)**: stop. Tell them to run the command above and that `.i2e/.serve.url` will appear when it's up. Skip steps 3–4.
3. Verify with a quick `curl -sS -o /dev/null -w "%{http_code}" <url>` — expect `200`.
4. Return to the user with: "Serving at <url> — open <url>#cap/<slug> to land on that capability"
5. The server runs detached until the user kills it (`i2e-serve stop`)

## Why the inline wrapper

**Do NOT** use `python -m i2e_core.serve start` for detached operation. The CLI calls `start_server()` (which spawns a daemon thread) and then returns — the parent process exits immediately, which kills the daemon thread. The `.serve.url` file is left behind pointing at a dead port.

The inline `-c` wrapper blocks the main thread with `threading.Event().wait()`, keeping the daemon serving thread alive until killed. That form is correct whether the user runs it in their own shell or Claude runs it via `Bash` `run_in_background: true`.

(Filing an intent to make the CLI `start` block on its own would let the command collapse to `python -m i2e_core.serve start`. Until then, the inline wrapper is the right form.)

## Stop
`python -m i2e_core.serve stop` — reads `.serve.url`, sends shutdown signal, removes the file. If you started the server via the inline wrapper above, `stop` works the same way (it posts to `/shutdown` over HTTP).
