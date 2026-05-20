# Task: Interactive authoring/edit flow

**Status:** [✓] Completed
**Completed:** 2026-05-19

**Dependencies:** task-01-skill-manifest

## Implementation Notes
- `src/i2e_core/intent_authoring.py` provides `intent_path`, `load_or_init`, `upsert_evidence`, `upsert_constraint`, `remove_item`, `save`.
- `upsert_*` and `remove_item` use `model_copy(update=...)` so they return new `Capability` instances rather than mutating.
- `remove_item` looks in both evidence and constraints and is a no-op when the id isn't found.
- `save()` runs the validation gate FIRST, then handles version-bump logic based on the on-disk copy's signature, then atomic-writes through `intent.write_intent`.
- A "Workflow recipes" section was added to the SKILL.md covering add capability / add evidence / retire item / draft→active / dry-run save.

## Context

The skill itself is markdown instructions for an LLM. The deterministic parts — read existing file, render template, validate, atomic-write — live as Python helpers under `i2e_core` so the LLM only handles the interactive prompts.

## Needed from User

None.

## Instructions

1. Add `src/i2e_core/intent_authoring.py`:
   - `def load_or_init(root: Path, slug: str, watcher: str) -> Capability` — returns existing intent or a fresh scaffold
   - `def upsert_evidence(cap: Capability, item: EvidenceItem) -> Capability` — adds or replaces by `id`
   - `def upsert_constraint(cap: Capability, c: Constraint) -> Capability`
   - `def remove_item(cap: Capability, item_id: str) -> Capability`
   - `def save(root: Path, cap: Capability, installed_providers: set[str], cfg: I2EConfig) -> Path` — validates first; raises `ValidationError` on failure; otherwise atomic-writes and returns the path
2. The save function bumps `version` automatically if the evidence/constraint lists changed materially compared to the on-disk copy (use a hash of the canonical YAML of those two lists)
3. Always set `frontmatter.updated = today_utc()` on save
4. Extend the SKILL.md with a "Workflow recipes" section listing common operations (add evidence, retire item, switch from draft → active)

## Acceptance Criteria

- [ ] `load_or_init` returns the scaffold for a new slug and the parsed file for an existing one
- [ ] `upsert_evidence` replaces by id (no duplicates)
- [ ] `save` refuses to write when validation fails (file on disk is unchanged)
- [ ] `save` bumps `version` when items change, leaves it alone for cosmetic edits (e.g. description text only)
- [ ] `save` always sets `updated` to today
