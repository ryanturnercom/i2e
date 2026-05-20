# Epic: Provider Framework & Initial Providers

**Status:** [✓] Completed
**Source spec:** .documentation/I2E_simplified.md
**Started:** 2026-05-19
**Completed:** 2026-05-19

## Context

Provider skills are how evidence gets collected. The spec is explicit:

> The installed skill set IS the provider registry. To add Sentry, you install `i2e-provider-sentry`. No central config file.

That makes the contract everything. Each provider must:

- Accept one evidence item
- Return one of three verdict shapes (Case, Target, Constraint)
- Follow the agentskills.io SKILL.md convention

This epic defines that contract and ships the two reference providers — `pytest` (sync; covers Cases + Constraints) and `human` (async; establishes the pending-file pattern reused by `survey`, `interview`, and any future async provider).

## Implementation Overview

- Define a Python ABC (`ProviderResult` dataclasses + `invoke(item, ctx) -> Result`) in `i2e_core.provider`
- Add a discovery helper that resolves a provider name → installed skill folder (`~/.claude/skills/i2e-provider-<name>/`)
- Ship `i2e-provider-pytest` — SKILL.md + a Python helper that runs `pytest <query>` and translates exit code into verdict
- Ship `i2e-provider-human` — SKILL.md + helper that writes a pending file and returns `awaiting_human`

The contract this epic locks in (return shapes, discovery rules, pending-file shape) is consumed by `i2e-evidence` (epic 05) and extended by epic 09 providers.

## Tasks

- [x] [task-01: Provider contract + result shapes](tasks/task-01-provider-contract.md)
- [x] [task-02: Provider discovery from installed skills](tasks/task-02-provider-discovery.md)
- [x] [task-03: i2e-provider-pytest skill + runner](tasks/task-03-provider-pytest.md)
- [x] [task-04: i2e-provider-human skill + pending writer](tasks/task-04-provider-human.md)
- [x] [task-05: Provider invocation tests](tasks/task-05-provider-tests.md)

## Outcome

Provider framework shipped and green. Skill-based registry is live: discovery walks `~/.claude/skills/` and `<project>/.claude/skills/`, with project-local overriding user-level. Both reference providers (`pytest` sync, `human` async) load and invoke cleanly through `load_provider(name)`.

**Modules added**
- `src/i2e_core/provider/__init__.py` — public API barrel
- `src/i2e_core/provider/contract.py` — `CaseResult`, `TargetResult`, `AsyncResult` dataclasses; `Provider` Protocol; `ProviderContext`; `to_item_verdict`
- `src/i2e_core/provider/discovery.py` — `installed_provider_names`, `load_provider`, mtime-keyed module cache, CLI helper at `python -m i2e_core.provider.discovery`
- `src/i2e_core/pending.py` — `PendingFile` model, `write_pending`, `read_pending`, `list_open_pending`, `list_resolved_pending`, `archive_pending`

**Skills installed**
- `.claude/skills/i2e-provider-pytest/` — SKILL.md + `provider.py` (subprocess via `sys.executable -m pytest`)
- `.claude/skills/i2e-provider-human/` — SKILL.md + `provider.py` (writes pending file, returns `awaiting_human`)

**Tests**
- 37 new provider tests under `tests/providers/`: contract, pytest provider, human provider, discovery priority
- Combined suite: **84 passed**, 0 failed, ~1s runtime
- Coverage on `src/i2e_core/` overall: **97%** (provider package 96%, pending 98%)
- `python -m i2e_core.provider.discovery` prints `human` and `pytest`, one per line

**Contract locked in for downstream epics**
- Provider result shapes (`CaseResult`/`TargetResult`/`AsyncResult`) and the converter `to_item_verdict` will be consumed by `i2e-evidence` (epic 05).
- Pending file shape (`PendingFile`) is the canonical async-provider contract — `i2e-adapt` (epic 06) will read resolved files via `list_resolved_pending` and archive them via `archive_pending`.
- Discovery cache is mtime-keyed; epic 09's additional providers will be picked up automatically without code changes.
