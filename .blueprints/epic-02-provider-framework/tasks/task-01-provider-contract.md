# Task: Provider contract + result shapes

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-03-intent-parser, task-05-evidence-writer (epic 01)

## Context

Spec §4.2 specifies three verdict shapes:

- Case: `{ verdict: pass | fail, output: "..." }`
- Target: `{ value: <observed>, met: true | false | trending, observed_at: <iso> }`
- Constraint: same shape as Case

This task defines the Python contract every provider helper module implements, plus the conversion from provider-shape into the `ItemVerdict` model used by `current.yaml`.

## Needed from User

None.

## Instructions

1. Create `src/i2e_core/provider/__init__.py` exposing the symbols below
2. Create `src/i2e_core/provider/contract.py`:
   - Dataclasses (or Pydantic models — pick one and be consistent):
     - `CaseResult`: `verdict: Literal["pass","fail"]`, `output: str = ""`
     - `TargetResult`: `value: str`, `met: Literal["met","unmet","trending"]`, `observed_at: datetime`
     - `AsyncResult`: `verdict: Literal["awaiting_human"]`, `pending: str` (basename)
   - `ProviderResult = CaseResult | TargetResult | AsyncResult`
   - `class Provider(Protocol)`:
     - `name: str`
     - `def invoke(self, item: EvidenceItem | Constraint, ctx: ProviderContext) -> ProviderResult: ...`
   - `class ProviderContext`: dataclass — `root: Path`, `capability: str`, `run_id: str`, `cfg: I2EConfig`
3. Add a converter `to_item_verdict(result: ProviderResult, *, prev_attempts: int = 0) -> ItemVerdict`:
   - Case `pass` → `ItemVerdict(verdict="pass", last_observed=now)`
   - Case `fail` → `ItemVerdict(verdict="fail", attempts_used=prev_attempts+1, last_observed=now, raw={"output": ...})`
   - Target `met` → `ItemVerdict(verdict="met", value=..., last_observed=observed_at)`
   - Target `unmet`/`trending` → corresponding verdict, increment `attempts_used`
   - Async → `ItemVerdict(verdict="awaiting_human", pending=...)`
4. Export from `i2e_core.provider`: `Provider`, `ProviderContext`, `ProviderResult`, `CaseResult`, `TargetResult`, `AsyncResult`, `to_item_verdict`

## Acceptance Criteria

- [x] All three result types instantiate and serialize via `dataclasses.asdict()` (or `model_dump()` if Pydantic)
- [x] `to_item_verdict` increments `attempts_used` for `fail`/`unmet`/`trending` and leaves it untouched for `pass`/`met`/`awaiting_human`
- [x] Importing `from i2e_core.provider import Provider, ProviderContext` works
- [x] Type checks pass with `mypy --strict` on `src/i2e_core/provider/`

## Implementation Notes

- Used `@dataclass` (frozen=False) for `CaseResult`, `TargetResult`, `AsyncResult`, and `ProviderContext` — ergonomic and small, per the task hint. The Pydantic boundary stays at `ItemVerdict` (persisted shape).
- `Provider` is `typing.Protocol` decorated with `@runtime_checkable` so tests can use `isinstance(obj, Provider)`.
- `to_item_verdict` is the only place that decides what bumps `attempts_used`. Async (`awaiting_human`) does NOT bump — the attempt only counts once a resolution lands.
- `AsyncResult.verdict` defaults to `"awaiting_human"` so callers only have to pass `pending=`.
