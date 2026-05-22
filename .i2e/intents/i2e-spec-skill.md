---
capability: i2e-spec-skill
created: '2026-05-20'
updated: '2026-05-21'
version: 1
status: shipped
watcher: '@ryan'
depends_on:
- intent-depends-on-field
- intent-touches-field
touches:
- src/i2e_core/spec.py
- tests/test_i2e_spec.py
- tests/fixtures/specs/**
- .claude/skills/i2e-spec/**
- .documentation/I2E_simplified.md
---

# `i2e-spec` skill - PRD/spec to many intents

There is no path from a feature PRD or design doc to a set of capability
intents today. `i2e-intent` is one-capability-at-a-time. Adding a multi-
section PRD by hand is friction.

New skill: `i2e-spec`. Inputs:
- A markdown doc (path or pasted text).

Outputs:
- `.i2e/specs/<slug>.md` - preserved spec, normalized header.
- N draft intent files under `.i2e/intents/`, each with frontmatter
  `spec: <slug>`, `spec_section: <ref>`, and populated `depends_on:` +
  `touches:` inferred from the spec.
- A decomposition log the human reviews before flipping any intent to
  active.

Companion subcommand `i2e-spec --reconcile <slug>`: re-runs decomposition
on the (possibly edited) spec, diffs against existing intents, proposes
add / edit / retire as pending files.

## Spec updates required
- Section 3: add `.i2e/specs/` to repo layout.
- Section 4.1: add `i2e-spec` to loop skills.
- Appendix B: add `i2e-spec` to the skill index.
- Section 2.1: frontmatter gains optional `spec:` and `spec_section:`.

## Evidence of success

- id: spec-to-intents-decomposes
  type: case
  provider: pytest
  query: tests/test_i2e_spec.py::test_fixture_prd_produces_expected_intents
  expect: passes
  effort: high

- id: spec-preserved-on-disk
  type: case
  provider: pytest
  query: tests/test_i2e_spec.py::test_original_spec_saved_under_dot_i2e_specs
  expect: passes
  effort: low

- id: decomposed-intents-link-back
  type: case
  provider: pytest
  query: tests/test_i2e_spec.py::test_each_intent_frontmatter_links_to_spec
  expect: passes
  effort: medium

- id: reconcile-detects-edit
  type: case
  provider: pytest
  query: tests/test_i2e_spec.py::test_reconcile_proposes_edit_when_spec_section_changes
  expect: passes
  effort: medium

- id: reconcile-detects-add-and-retire
  type: case
  provider: pytest
  query: tests/test_i2e_spec.py::test_reconcile_proposes_add_and_retire_on_section_set_change
  expect: passes
  effort: medium

- id: decomposed-fills-depends-on
  type: case
  provider: pytest
  query: tests/test_i2e_spec.py::test_decomposition_populates_depends_on_from_spec_order
  expect: passes
  effort: medium

- id: spec-mentions-i2e-spec-skill
  type: case
  provider: pytest
  query: tests/test_i2e_spec.py::test_spec_doc_lists_i2e_spec_skill_in_appendix_b
  expect: passes
  effort: low

## Constraints

- id: intents-land-as-draft
  provider: pytest
  query: tests/test_i2e_spec.py::test_all_decomposed_intents_have_status_draft
  expect: passes
  effort: low

- id: existing-i2e-intent-unchanged
  provider: pytest
  query: tests/test_i2e_spec.py::test_single_intent_workflow_still_works
  expect: passes
  effort: low
