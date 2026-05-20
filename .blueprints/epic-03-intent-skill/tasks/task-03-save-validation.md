# Task: Save-time validation gate

**Status:** [✓] Completed
**Completed:** 2026-05-19

**Dependencies:** task-02-authoring-flow

## Implementation Notes
- `src/i2e_core/intent_save_gate.py::gate(cap, root, *, extra_skill_paths=None)` loads config, resolves installed providers, calls `validate_capability_with_config`, and re-wraps errors with the capability slug prefix.
- Error messages now read like `shorten-url > redirect-latency-p95: Item 'redirect-latency-p95' names provider 'datadog' but no matching i2e-provider-* skill is installed (scanned ~/.claude/skills, ./.claude/skills)`.
- The discovery-scanned hint is appended only to "no matching i2e-provider-* skill is installed" errors so other errors stay clean.
- `save()` calls `gate` exactly once (no double validation) before deciding on version-bump and writing.
- `dry_run=True` runs the gate (so callers still see errors) and returns the target path without touching disk.
- `extra_skill_paths` plumb-through lets tests inject fake skills dirs without monkeypatching, though the test suite primarily monkeypatches `installed_provider_names` for full hermeticity.

## Context

Spec §5 — the three forced-evidence rules must run on every intent edit. Combine `validate_capability_with_config` (effort tiers) with provider discovery so rule 2 actually catches unknown providers.

## Needed from User

None.

## Instructions

1. Add `src/i2e_core/intent_save_gate.py`:
   - `def gate(cap: Capability, root: Path) -> None`:
     - Loads config (`load_config(root)`)
     - Resolves installed providers (`installed_provider_names()` scanning user + project skills dirs)
     - Calls `validate_capability_with_config(cap, cfg, installed_providers)`
     - Raises `ValidationError` (from epic 01) if anything fails
2. Wire it into `intent_authoring.save` — `save` calls `gate` before writing
3. The validator's error message must include the offending intent's file path and item id, e.g. `shorten-url > redirect-latency-p95: provider "datadog" not installed (scanned ~/.claude/skills, ./.claude/skills)`
4. Add a "dry-run" mode in `save(..., dry_run=True)` that runs the gate and returns the would-be path without writing

## Acceptance Criteria

- [ ] Saving an intent with unknown provider raises `ValidationError` and lists the provider name
- [ ] Saving an intent with an unknown effort tier raises `ValidationError`
- [ ] Saving an intent with zero items raises `ValidationError`
- [ ] Dry-run mode returns the target path without touching the filesystem
- [ ] Error messages always include the capability slug and item id
