# Task: Develop workflow (intent → src/)

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-01-skill-manifest, task-02-context-loader

## Context

Develop is mostly LLM work, but a few deterministic pieces support it: diff resolution against prior evidence, src/tests path conventions, and an output summary the orchestrator can log.

## Needed from User

None.

## Instructions

1. Flesh out `src/i2e_core/develop.py`:
   - `def diff_against_current(root: Path, capability: str) -> DevelopDiff`:
     - `DevelopDiff(BaseModel)`: `prior_version: int | None`, `current_version: int`, `new_items: list[str]`, `changed_items: list[str]`, `removed_items: list[str]`, `last_failures: list[tuple[str, str]]` (item_id, reason from last evidence run)
   - `def suggested_src_paths(cap: Capability) -> list[Path]`:
     - Convention: a capability `shorten-url` ⇒ `src/<slug-as-pkg>/__init__.py` (slug `_` substituted for `-`); the LLM is free to override, but the helper provides the default
   - `def suggested_test_paths(item: EvidenceItem) -> Path`:
     - For pytest provider queries like `tests/foo.py::test_bar`, returns `Path("tests/foo.py")`
2. Add `def develop_summary(diff: DevelopDiff, files_touched: list[Path]) -> str` — used by the orchestrator to write the tick log
3. Wire the SKILL.md "Workflow" section to reference these helpers explicitly

## Acceptance Criteria

- [✓] `diff_against_current` returns `prior_version=None` for a capability with no prior `current.yaml`
- [✓] `diff_against_current` correctly identifies added/removed items by id when prior evidence exists
- [✓] `suggested_src_paths` produces hyphen-to-underscore slug paths
- [✓] `suggested_test_paths` extracts the file portion from a pytest nodeid
- [✓] `develop_summary` produces a single-line log entry suitable for `.i2e/logs/<tick>.yaml`

## Implementation Notes

- `DevelopDiff` is a Pydantic v2 `BaseModel` (consistent with the rest of the
  codebase) with `extra="forbid"`.
- `diff_against_current` uses set algebra on item ids: `new_items` are in the
  intent but not in `current.yaml`'s items map; `removed_items` are the
  inverse. `changed_items` is populated only when the intent's version has
  advanced past the recorded `intent_version` — since we don't store prior
  intents, version-bump is the only deterministic "something is different"
  signal we have for items that exist in both sides.
- `last_failures` reads `current.items` for verdicts in `{fail, unmet,
  trending}` and grabs `raw.error` (preferred) or `raw.output` (fallback).
- `suggested_src_paths(cap)` returns `[Path(f"src/{slug.replace('-','_')}/__init__.py")]`
  — a single-element list (per the per-capability heuristic in the brief).
- `suggested_test_paths` accepts either an `EvidenceItem` or a `Constraint`
  (they share a duck-typed `provider`/`query` shape) and returns `None` for
  non-pytest providers.
- `develop_summary` produces one-line output with three branches: first
  develop (no prior version), version bump, and no-version-bump.
