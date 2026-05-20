# Claude Code instructions

This is **Intent-to-Evidence (Simplified)** — a skills-driven SDLC where humans declare intent and an AI agent runs the IDEA loop (Intent → Develop → Evidence → Adapt). The full spec lives at `.documentation/I2E_simplified.md`. Read it before making non-trivial changes.

## Project layout

```
src/i2e_core/         deterministic Python core (Pydantic v2 throughout)
tests/                pytest suite — uses tmp_path; never touches real .i2e/
.i2e/                 this project's own intent + evidence (mostly empty)
.claude/skills/       loop skills (i2e, i2e-intent, ...) + provider skills
.blueprints/          execution history; one folder per epic (09 total, all green)
.documentation/       canonical spec — source of truth
examples/             working demos that use i2e_core (e.g. url-shortener)
```

## Run things

Python: 3.11+. Editable install in `.venv/`.

```powershell
./tasks.ps1 install     # one-time: python -m venv + pip install -e .[dev]
./tasks.ps1 test        # pytest -q (excludes the e2e marker)
./tasks.ps1 cov         # pytest --cov=i2e_core --cov-report=term-missing
./tasks.ps1 e2e         # pytest -m e2e (the spec §10 worked example)
./tasks.ps1 all         # test + e2e
```

Or directly: `.venv\Scripts\python.exe -m pytest -q`.

## Conventions (non-obvious)

- **Pydantic v2** for every data model. Use `ConfigDict(extra="forbid")` on new models.
- **Atomic writes**: `io_utils.atomic_write` (sibling `.tmp` + `os.replace`). `os.replace` is atomic on Windows and POSIX.
- **YAML**: `dump_yaml` from `io_utils` — never `yaml.dump` directly (kills key order).
- **Run-ids**: `runid.new_run_id()` produces `YYYY-MM-DD-<6 hex>`. Never invent your own format.
- **No mocks in production code**. Tests use `FakeProvider` patterns; the runtime always calls real providers.
- **Coverage gate**: 85% on `src/i2e_core/`. Anything below fails review.

## Boundary rules (enforced by the architecture — don't break them)

| Skill | May write |
|---|---|
| `i2e-intent` | `.i2e/intents/**` |
| `i2e-develop` | `src/**`, `tests/**` |
| `i2e-evidence` | `.i2e/evidence/**`, `.i2e/pending/**` (via async providers) |
| `i2e-adapt` | `.i2e/pending/**`, `.i2e/logs/**`. Single intent-file carve-out: `apply_resolutions` may edit `.i2e/intents/**`. Documented at both call sites. |
| `i2e` (orchestrator) | `.i2e/logs/**`, `.i2e/report.html`, plus whatever the dispatched skill writes |
| `i2e-report` | `.i2e/report.html` only — deterministic Python, zero LLM tokens |
| `i2e-serve` | `.i2e/.serve.url` (and only that) |

## Provider contract (locked in epic 02)

- Cases / Constraints → `CaseResult(verdict: pass|fail, output)`
- Targets → `TargetResult(value, met: met|unmet|trending, observed_at)`
- Async → `AsyncResult(verdict="awaiting_human", pending=<basename>)`

Provider skills live at `.claude/skills/i2e-provider-<name>/` with `SKILL.md` + `provider.py` exposing a module-level `provider` instance. Discovery picks them up automatically.

## When in doubt

- Spec disagrees with code → trust the spec; file an intent to fix the code.
- New behavior → start by writing an intent in `.i2e/intents/`. Evidence comes after.
- A test fails after a refactor → fix root cause; do NOT mark it `xfail` to make CI green.
