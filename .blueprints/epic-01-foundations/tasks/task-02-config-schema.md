# Task: Config schema + loader

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-01-project-skeleton

## Context

`.i2e/config.yaml` holds effort tiers, defaults (case_effort, target_effort, watcher), and advisory scheduler config (spec §2.3). The loader must:

- Return strongly-typed config (Pydantic models)
- Apply built-in defaults when the file is missing or partial (greenfield projects work without writing a config file)
- Resolve an item's `effort` tier into its `max_attempts`, given the item's `type` (case | target)

Language: Python 3.11+ — Pydantic v2.

## Needed from User

None.

## Instructions

1. Create `src/i2e_core/config.py` with Pydantic models:
   - `TierBudget(BaseModel)`: `max_attempts: int`
   - `EffortTiers(BaseModel)`: `case: dict[str, TierBudget]`, `target: dict[str, TierBudget]`
   - `Defaults(BaseModel)`: `case_effort: str = "medium"`, `target_effort: str = "low"`, `watcher: str = "@me"`
   - `SchedulerConfig(BaseModel)`: `cadence: str = "weekly"`, `via: str = "claude-code-routine"`
   - `I2EConfig(BaseModel)`: `effort_tiers: EffortTiers`, `defaults: Defaults`, `scheduler: SchedulerConfig`
2. Provide built-in defaults that match spec §2.3:
   - case tiers: `lazy=0, low=3, medium=6, high=10`
   - target tiers: `lazy=0, low=1, medium=3, high=5`
3. Loader API:
   - `load_config(root: Path | None = None) -> I2EConfig` — reads `<root>/.i2e/config.yaml` if present, otherwise returns defaults. Partial files merge with defaults (do NOT require user to specify every tier).
   - `resolve_max_attempts(cfg: I2EConfig, item_type: Literal["case","target","constraint"], effort: str) -> int` — constraints share the case budget map.
4. Write a sample `.i2e/config.yaml` (commented; the spec's example is fine) — but do NOT make the loader require it.

## Acceptance Criteria

- [✓] `load_config()` returns defaults when `.i2e/config.yaml` is absent
- [✓] `load_config()` returns merged values when the file is present with partial keys
- [✓] `resolve_max_attempts(cfg, "case", "medium") == 6` with defaults
- [✓] `resolve_max_attempts(cfg, "target", "lazy") == 0` with defaults
- [✓] Invalid effort names raise a clear `ValueError` (not a KeyError)
- [✓] Constraints use the case budget map

## Implementation Notes

- `src/i2e_core/config.py` defines `TierBudget`, `EffortTiers`, `Defaults`, `SchedulerConfig`, and `I2EConfig`.
- Built-in defaults live in `_default_dict()`; `load_config()` deep-merges any user file over them so partial config files work.
- `resolve_max_attempts` maps `constraint` to the case tier set, raises `ValueError` for unknown efforts and item types.
- A sample `.i2e/config.yaml` is committed for reference but is not required by the loader.
