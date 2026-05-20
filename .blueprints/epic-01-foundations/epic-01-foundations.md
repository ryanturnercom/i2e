# Epic: Foundations & Shared Core

**Status:** [✓] Completed
**Source spec:** .documentation/I2E_simplified.md
**Started:** 2026-05-19
**Completed:** 2026-05-19

## Context

The Intent-to-Evidence (Simplified) system is a skills-driven SDLC where humans declare intent in Capability files and an AI agent runs the IDEA loop. Before any loop skill can be built, the project needs:

- A standard repo layout (`src/`, `tests/`, `.i2e/`)
- A typed model + parser for Capability intent files (frontmatter + Evidence + Constraints sections)
- A validator that enforces forced-evidence rules
- A writer for the evidence artifacts (`current.yaml` + `runs/<id>.yaml`)
- A config loader for `.i2e/config.yaml`
- Shared utility helpers (run-id, path resolution, atomic writes)

These are reused by every downstream loop and provider skill. Everything else depends on this epic.

## Implementation Overview

Build a single Python package — call it `i2e_core` — under `src/i2e_core/`. It exposes:

- `intent.py` — parser, Pydantic models for Capability, EvidenceItem, Constraint
- `validator.py` — the three forced-evidence rules
- `config.py` — `.i2e/config.yaml` loader with effort-tier resolution
- `evidence.py` — read/write `current.yaml` and `runs/<id>.yaml`
- `paths.py` — canonical path resolver (root, intents dir, evidence dir, pending dir, logs dir)
- `runid.py` — date-prefixed slug generator
- `io_utils.py` — atomic file writes, YAML dumpers with stable key order

Loop skills (epics 03–08) import from `i2e_core`. Provider skills (epic 02 + 09) also import from it for the verdict shape.

## Tasks

- [✓] [task-01: Project skeleton + pyproject + repo layout](tasks/task-01-project-skeleton.md)
- [✓] [task-02: Config schema + loader](tasks/task-02-config-schema.md)
- [✓] [task-03: Intent file parser + Pydantic models](tasks/task-03-intent-parser.md)
- [✓] [task-04: Forced-evidence validator](tasks/task-04-intent-validator.md)
- [✓] [task-05: Evidence read/write (current.yaml + runs/)](tasks/task-05-evidence-writer.md)
- [✓] [task-06: Shared utils (paths, run-id, atomic writes)](tasks/task-06-shared-utils.md)
- [✓] [task-07: pytest setup + foundation tests](tasks/task-07-pytest-setup.md)

## Outcome

- `pytest -q` → **47 passed**.
- Coverage on `src/i2e_core/` → **97%** (target was >85%).
- Acceptance gate (`python -m venv .venv` → `pip install -e .[dev]` → `pytest -q`) is green end-to-end.
