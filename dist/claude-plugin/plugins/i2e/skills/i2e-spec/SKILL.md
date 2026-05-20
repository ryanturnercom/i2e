---
name: i2e-spec
description: Decompose a PRD or design doc into N draft capability intents. Preserves the source spec under .i2e/specs/ and links each intent back via spec/spec_section frontmatter. Reconcile mode diffs the spec against existing intents.
license: Apache-2.0
metadata:
  tier: loop
  version: "0.1.0"
---

# i2e-spec

The bulk authoring step. `i2e-intent` is one-capability-at-a-time;
`i2e-spec` takes a multi-section PRD and produces a draft intent per
section in one shot, with `depends_on:` populated from the section order.
Nothing flips to `active` automatically — the human reviews the
decomposition log and walks the drafts through `i2e-intent` (or activates
them directly) once happy.

## When to use
- The user pastes or links a PRD / design doc they want to break into
  capabilities.
- A spec has been edited and the on-disk intents need to catch up
  (`i2e-spec --reconcile <slug>`).
- An external doc (Notion, Linear, Jira) has been exported as markdown
  and needs the same treatment.

## Inputs
- `slug`: kebab-case identifier for the spec (also the filename under
  `.i2e/specs/`).
- One of:
  - `path`: filesystem path to a markdown document.
  - `text`: inline markdown the user pasted.

## Outputs
- `.i2e/specs/<slug>.md` — the spec preserved verbatim (header normalized
  but body untouched).
- N draft intent files under `.i2e/intents/`, each with
  `spec: <slug>`, `spec_section: <ref>`, `depends_on: [<prev-slug>]`,
  and a stub `touches:` derived from the slug.
- A decomposition log printed to the conversation so the human can spot
  bad slug choices before activating.

## Boundaries
- READ: the input markdown, any prior `.i2e/specs/<slug>.md`, any
  intents under `.i2e/intents/` that already declare `spec: <slug>`.
- WRITE: `.i2e/specs/<slug>.md` and the decomposed intents.
- NEVER WRITE: src/**, tests/**, evidence or pending files.

## Workflow

### First-time decomposition
1. Accept the spec body (file or pasted text).
2. Call `i2e_core.spec.save_decomposition(root, prd, slug=<slug>)`.
3. Display the resulting intent list so the user can:
   - Adjust slugs (rename intent files + update `depends_on:` refs).
   - Promote any intent to active via `i2e-intent` once cases are
     fleshed out (the stub case is a placeholder).

### Reconcile after the spec edits
1. Call `i2e_core.spec.reconcile(root, <slug>)`.
2. For each :class:`ReconcileAction`, write a pending file under
   `.i2e/pending/` describing the proposed change (add / edit / retire).
3. The human resolves each pending file; on the next `/i2e` tick the
   orchestrator applies the resolutions.

## Forbidden
- Activating intents directly. Decomposition lands them as `draft` and
  the human reviews before they enter the loop.
- Inferring evidence items from the prose. The stub case is intentional
  — `i2e-intent` is the place where evidence gets real.
- Writing under `src/` or `tests/`. The skill is intent-shaped, not
  develop-shaped.

## Python helpers (the deterministic core)
- `i2e_core.spec.slugify(title) -> str`
- `i2e_core.spec.decompose(prd, slug=<slug>) -> list[Capability]`
- `i2e_core.spec.save_decomposition(root, prd, slug=<slug>) -> list[Path]`
- `i2e_core.spec.reconcile(root, slug) -> list[ReconcileAction]`
