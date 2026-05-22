---
name: i2e-intent
description: Author or edit a Capability intent file in .i2e/intents/. Validates on save against forced-evidence rules. The only skill that touches draft intents.
license: Apache-2.0
metadata:
  tier: loop
  version: "0.1.0"
---

# i2e-intent

Walks the user through authoring or editing one Capability file. Refuses to save invalid intents (missing provider, unknown provider, zero evidence items, or a human/subjective provider on a non-target item).

## When to use
- The user says "I want to add a capability called X"
- The user wants to add evidence to an existing capability
- A bug needs to become a Case (spec §10)

## Inputs
- Capability slug (kebab-case)
- Status (`draft` | `active` | `retired`)
- One or more Evidence items / Constraints

## Outputs
- `.i2e/intents/<slug>.md` (created or updated)
- Validation report (empty on success)

## Item types
Each evidence item is a **case** or a **target** (spec §2.2). A case is
something the agent verifies itself, programmatically (`provider: pytest`).
A target needs a provider, the passage of time, or a human — and
**anything a human must judge is a target**. `provider: human` and
`provider: survey` are valid only on `type: target`; the save gate rejects
them on a case or a constraint.

## Workflow
1. Resolve or prompt for the capability slug
2. Load existing intent if present (else start from a template via `i2e_core.intent_template.default_capability`)
3. Walk through evidence + constraint items (add / edit / remove) using the `i2e_core.intent_authoring` helpers
4. Run the save gate (`i2e_core.intent_save_gate.gate`) which calls `validate_capability_with_config(...)` with installed providers
5. If invalid, show errors and refuse to save (the human resolves before the file lands)
6. If valid, bump `version` when material changes occurred, set `updated` to today, atomic-write the file

## Workflow recipes

### Add a new capability
1. Pick a kebab-case slug (e.g. `shorten-url`).
2. Call `intent_authoring.load_or_init(root, slug, watcher)` to get a scaffold.
3. Walk the user through one or more evidence items / constraints with `upsert_evidence` / `upsert_constraint`.
4. Call `intent_authoring.save(root, cap, ...)` — the save gate runs validation and writes the file atomically.

### Add evidence to an existing capability
1. Call `load_or_init` for the existing slug — you get back the parsed file.
2. `upsert_evidence(cap, new_item)` appends-or-replaces by `id`.
3. `save(root, cap, ...)` — version auto-bumps because the evidence list changed materially.

### Retire an item
1. `cap = load_or_init(root, slug, watcher)`
2. `cap = remove_item(cap, item_id)` (idempotent — safe to call with unknown id)
3. `save(...)` — bumps version because the items signature changed.

### Switch from draft → active
1. `cap = load_or_init(root, slug, watcher)`
2. `cap.frontmatter.status = "active"`
3. `save(...)` — status changes do not bump version; only items signature changes do. `updated` still gets refreshed.

### Dry-run a save
Pass `dry_run=True` to `save(...)`. The gate still runs (so the user sees any validation errors), and the would-be file path is returned, but nothing is written.

## Python helpers (the deterministic core)
- `i2e_core.intent_template.default_capability(slug, watcher) -> Capability`
- `i2e_core.intent_authoring.load_or_init(root, slug, watcher) -> Capability`
- `i2e_core.intent_authoring.upsert_evidence(cap, item) -> Capability`
- `i2e_core.intent_authoring.upsert_constraint(cap, c) -> Capability`
- `i2e_core.intent_authoring.remove_item(cap, item_id) -> Capability`
- `i2e_core.intent_authoring.save(root, cap, *, dry_run=False) -> Path`
- `i2e_core.intent_save_gate.gate(cap, root) -> None` (raises `ValidationError` on failure)
- `i2e_core.intent.items_signature(cap) -> str`
- `i2e_core.intent.diff_summary(old, new) -> str`
