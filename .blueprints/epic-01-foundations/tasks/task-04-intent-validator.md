# Task: Forced-evidence validator

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-03-intent-parser

## Context

Spec §5 — three rules that determine if a Capability is invalid:

1. Any evidence item omits `provider`
2. Any evidence item names a provider with no matching installed `i2e-provider-*` skill
3. The Capability has zero evidence items

Pydantic catches rule 1 at parse time. Rule 3 is a length check. Rule 2 needs a provider-discovery hook — which doesn't exist yet (epic 02). For this task, accept an injectable `installed_providers: set[str]` so the validator is testable in isolation.

## Needed from User

None.

## Instructions

1. Create `src/i2e_core/validator.py`:
   - `class ValidationError(Exception)` with `.errors: list[str]`
   - `validate_capability(cap: Capability, installed_providers: set[str] | None = None) -> None` — raises `ValidationError` with all problems aggregated (don't fail on the first one)
2. Rules:
   - Rule 1: covered by Pydantic; surface a friendly message if it slips through (e.g. legacy file)
   - Rule 2: if `installed_providers is None`, **skip** rule 2 (caller opts in). When provided, every `item.provider` must be a member.
   - Rule 3: `len(cap.evidence) + len(cap.constraints) == 0` ⇒ error message "Capability has no evidence or constraints — every intent needs at least one way to know it worked"
3. Also validate effort tier names against the loaded `I2EConfig`:
   - `validate_capability_with_config(cap, cfg, installed_providers=None)` — wrapper that checks each item's effort exists in `cfg.effort_tiers.<type>`
4. CLI-facing helper: `format_errors(err: ValidationError) -> str` returning a human-readable block (bullet list with file path + item id)

## Acceptance Criteria

- [✓] A Capability with 0 items and 0 constraints raises `ValidationError` with rule 3 message
- [✓] Passing `installed_providers={"pytest"}` accepts pytest providers, rejects unknown ones, lists all unknowns in `.errors`
- [✓] `installed_providers=None` skips rule 2 (validator runs without provider registry)
- [✓] `validate_capability_with_config` rejects effort `"sky-high"` with a clear message
- [✓] All errors are aggregated — one call returns every problem, not just the first

## Implementation Notes

- `src/i2e_core/validator.py` defines `ValidationError(Exception)` with `.errors: list[str]`, plus `validate_capability`, `validate_capability_with_config`, and `format_errors`.
- Rule 1 is Pydantic-enforced; the surface message exists for defensive cases (empty provider strings).
- Rule 2 is opt-in via the `installed_providers` argument; constraints share the case effort map for tier validation.
- `validate_capability_with_config` re-raises a single aggregated `ValidationError` whose `.errors` includes both forced-evidence problems and effort-tier mismatches.
