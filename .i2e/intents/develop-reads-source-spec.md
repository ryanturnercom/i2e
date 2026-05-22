---
capability: develop-reads-source-spec
created: '2026-05-21'
updated: '2026-05-21'
version: 1
status: retired
watcher: '@ryan'
---

# Develop reads the source spec when one exists

When `i2e-spec` decomposes a PRD into intents, it saves the source under
`.i2e/specs/<slug>.md` and stamps each derived intent's frontmatter with
`spec:` (and optionally `spec_section:`). Today the `i2e-develop` skill
only reads the structured intent + `.i2e/context/`, so the narrative
rationale that *produced* the cases and constraints is invisible at build
time.

That's especially harmful for parallel fan-out: each sub-agent gets only
one capability's intent, with no other channel for the wider design
intent. Closing the gap means develop must open `.i2e/specs/<slug>.md`
whenever the intent's frontmatter points at one.

Scope of this capability: **SKILL.md only.** Extend the declared READ
surface to include `.i2e/specs/<slug>.md`, and add a workflow step that
instructs the skill to read it (preferring `spec_section` when present).
No core code change.

## Evidence of success

- id: skill-md-mentions-specs-read
  type: case
  provider: pytest
  query: tests/test_develop_reads_source_spec.py::test_skill_md_declares_spec_read
  expect: passes
  effort: low

- id: skill-md-has-workflow-step-for-spec
  type: case
  provider: pytest
  query: tests/test_develop_reads_source_spec.py::test_skill_md_workflow_step_for_spec
  expect: passes
  effort: low

- id: bundled-skill-stays-in-sync
  type: case
  provider: pytest
  query: tests/test_develop_reads_source_spec.py::test_bundled_skill_md_matches_source
  expect: passes
  effort: low

## Constraints

- id: read-surface-does-not-grow-write-surface
  provider: pytest
  query: tests/test_develop_reads_source_spec.py::test_write_surface_unchanged
  expect: passes
  effort: low
