# Task: Localhost HTTP server + SSE updates

**Status:** [ ] Pending

**Dependencies:** task-05-serve-skill-manifest, task-03-view-model

## Context

A tiny server that serves the rendered HTML and pushes SSE events on `.i2e/` mtime changes. Stdlib only where possible. `watchdog` for filesystem events.

## Needed from User

None.

## Instructions

1. Implement `src/i2e_core/serve.py`:
   - `start_server(root, host="127.0.0.1") -> str`:
     - Refuse if host != "127.0.0.1" (raise `ValueError`)
     - Bind ephemeral port via stdlib `http.server.ThreadingHTTPServer`
     - GET `/` → re-renders the report each request and returns the HTML (cheap because deterministic)
     - GET `/events` → SSE stream; on each `.i2e/` mtime change, send `event: change\ndata: <path>\n\n`
     - Use `watchdog.observers.Observer` to watch `.i2e/` recursively
     - Inject a tiny `<script>` into the rendered HTML at serve time that subscribes to `/events` and triggers `location.reload()` (the simplest reactive surface; no fancy diffing)
     - Write `.i2e/.serve.url` with `http://127.0.0.1:<port>/`
     - Return the URL
   - `stop_server(root)`:
     - Read `.serve.url`, parse port, send a `POST /shutdown` to the server (the server has a `/shutdown` route that calls `server.shutdown()`)
     - Delete `.i2e/.serve.url`
2. The server runs in a detached thread (or via `multiprocessing` if cleaner) so the skill returns immediately
3. CLI: `python -m i2e_core.serve start|stop`

## Acceptance Criteria

- [ ] `start_server` returns a URL like `http://127.0.0.1:<port>/`
- [ ] Hitting `/` returns HTML containing the project's capabilities
- [ ] `/events` returns `text/event-stream` content-type
- [ ] Modifying any file under `.i2e/` triggers an SSE event observed by a test client
- [ ] `stop_server` removes `.i2e/.serve.url` and shuts the server down
- [ ] Attempting to bind a non-loopback host raises `ValueError`
