# Example: URL shortener (file-system store)

A tiny web URL shortener that demonstrates Intent-to-Evidence on a real, runnable project. Storage is a single JSON file on disk — no database, no infrastructure.

## Layout

```
examples/url-shortener/
├── .i2e/
│   ├── intents/shorten-url.md      one Capability with 3 cases + 1 constraint
│   ├── context/ARCHITECTURE.md     standing reference for develop
│   ├── config.yaml                 effort tiers (uses defaults)
│   └── (evidence/, pending/, logs/ written by the loop)
├── src/shortener/
│   ├── store.py                    atomic file-system JSON store
│   ├── service.py                  shorten / resolve / safety check
│   └── server.py                   stdlib http.server, two routes
├── tests/
│   ├── test_shorten.py             the 3 cases referenced by the intent
│   ├── adversarial/test_open_redirect_blocked.py   the constraint
│   └── test_server.py              end-to-end HTTP test
├── conftest.py                     puts src/ on sys.path
└── data/                           created on first run (gitignored)
```

## Run the loop

From this directory:

```powershell
# 1. Run pytest directly to see all cases + the constraint pass
../../.venv/Scripts/python.exe -m pytest -q

# 2. Run i2e-evidence against the capability
../../.venv/Scripts/python.exe -m i2e_core.evidence_runner shorten-url

# 3. Run the orchestrator (preflight + decide + tick)
../../.venv/Scripts/python.exe -m i2e_core.orchestrator

# 4. Open the rendered dashboard
start .i2e/report.html
```

## Run the server

```powershell
../../.venv/Scripts/python.exe -m shortener.server --port 8765
```

Then in another shell:

```powershell
# Shorten a URL
curl -X POST http://127.0.0.1:8765/shorten -H "Content-Type: application/json" -d '{\"url\":\"https://example.com/long/path\"}'

# Follow the redirect
curl -L http://127.0.0.1:8765/<code>
```

## How this demonstrates I2E

- **Intent first.** `shorten-url.md` declares 3 cases + 1 constraint, each with a `provider: pytest` query. The code exists only to make those true.
- **Forced evidence.** Every claim ("returns 7-char code", "round-trip resolves", "no open redirect") has a named test that runs every time the loop ticks. Nothing is aspirational.
- **Constraint = invariant.** `no-open-redirect` is `effort: high`, so the loop will retry up to 10 times before escalating — the system is biased against shipping a vulnerable URL shortener.
- **Bug → Case (spec §10).** If someone reports "I can shorten `javascript:`", you add a new entry under Evidence/Constraints pointing at a new pytest test. Once green, the bug cannot recur.
