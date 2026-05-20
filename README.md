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

## Quickstart

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .[dev]
.venv\Scripts\python.exe -m pytest -q
```

Run the test suite via `tasks.ps1`:

```powershell
./tasks.ps1 test
```

## Redistributable bundles

The 13 skills can be packaged for distribution as a Claude Code plugin
marketplace and as an [agentskills.io](https://agentskills.io)-format pack:

```powershell
./tasks.ps1 bundle      # writes dist/claude-plugin/, dist/agentskills/, and zips
```

See `dist/README.md` (after build) for the publishing flow. Source of truth
remains `.claude/skills/` — re-run the bundle command after editing any
`SKILL.md` or `provider.py`.
