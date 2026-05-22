# Intent-to-Evidence (Simplified)

A small, agent-native SDLC: humans declare intent, an AI agent builds and proves it, evidence is forced, and the loop never ends. See the full source specification at [.documentation/I2E_simplified.md](.documentation/I2E_simplified.md).

## Loop skills

- `i2e` — orchestrator (preflight + one-step advance)
- `i2e-intent` — author or edit Capability files
- `i2e-develop` — build code in `src/` from intents
- `i2e-evidence` — invoke providers, write `current.yaml` + `runs/`
- `i2e-adapt` — budgeted auto-improvement; pending on exhaustion
- `i2e-report` — render static `.i2e/report.html`
- `i2e-serve` — optional localhost server with live SSE updates

## Reference providers

- `i2e-provider-pytest` — cases and constraints via the test runner
- `i2e-provider-human` — subjective acceptance for cases or targets
- `i2e-provider-survey` — numeric-scale survey (NPS / Likert) targets
- `i2e-provider-datadog` — metric-window targets via the Datadog API
- `i2e-provider-ga` — GA4 Data API metric targets
- `i2e-provider-sentry` — Sentry event-count cases or targets

## Quickstart

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .[dev]
.venv\Scripts\python.exe -m pytest -q
```

Or via `tasks.ps1`:

```powershell
./tasks.ps1 install     # create .venv + editable install with dev extras
./tasks.ps1 test        # pytest -q (excludes the e2e marker)
./tasks.ps1 cov         # coverage on src/i2e_core
./tasks.ps1 e2e         # spec §10 worked example
./tasks.ps1 all         # test + e2e
```

A working downstream example lives at [`examples/url-shortener/`](examples/url-shortener/).

## Live report server

`i2e-serve` binds `127.0.0.1` on a static port (default `4230`) and opens the
report in your default browser:

```powershell
.venv\Scripts\python.exe -m i2e_core.serve start
# or, with overrides
.venv\Scripts\python.exe -m i2e_core.serve start --port 8080 --no-browser
```

Override the defaults in `.i2e/config.yaml`:

```yaml
serve:
  port: 4230            # any free TCP port; pass --port to override per-launch
  open_browser: true    # set false to suppress auto-open
```

Stop it with `python -m i2e_core.serve stop` (reads `.i2e/.serve.url`).

## Redistributable bundles

The 13 skills can be packaged for distribution as a Claude Code plugin
marketplace and as an [agentskills.io](https://agentskills.io)-format pack:

```powershell
./tasks.ps1 bundle      # writes dist/claude-plugin/, dist/agentskills/, and zips
```

See `dist/README.md` (after build) for the publishing flow. Source of truth
remains `.claude/skills/` — re-run the bundle command after editing any
`SKILL.md` or `provider.py`.

## Releasing

Use the `/release` slash command in Claude Code to bump the version in
`pyproject.toml` (the single source of truth), rebuild bundles, commit,
tag, and push to `origin/main`. Default bump is `patch`; pass `minor` or
`major` to bump those components.
