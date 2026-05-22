---
capability: console-intent-and-writes
created: '2026-05-21'
updated: '2026-05-22'
version: 1
status: shipped
watcher: '@ryan'
depends_on:
- console-foundation
touches:
- src/i2e_core/console/views/intent.py
- src/i2e_core/console/views/pending.py
- src/i2e_core/console/actions/promote.py
- src/i2e_core/console/actions/resolve.py
- src/i2e_core/console/templates/intent/**
- src/i2e_core/console/templates/pending/**
- src/i2e_core/console/templates/fragments/**
- src/i2e_core/intent_authoring.py
- src/i2e_core/pending.py
- tests/console/**
- CLAUDE.md
spec: i2e-console
spec_section: '2'
---

The intent detail view, the pending view, and the two narrow write
endpoints that let an operator drive the IDEA loop from the console
without bypassing the methodology.

Boundary carve-out for `i2e-serve`: status-field-only edits on
`.i2e/intents/<slug>.md` (via `intent_authoring.promote_intent`) and
resolution-block-only writes on `.i2e/pending/<file>.yaml` (same shape
`i2e-adapt.apply_resolutions` reads). CLAUDE.md boundary table updates
accordingly; both call sites carry a comment documenting the carve-out.

Scope:
- Intent detail view (`/intent/<slug>`, split layout): header, in-flight
  workers strip, pending strip, evidence table (cases / targets /
  constraints expandable to provider / query / expect / window / attempts
  / last verdict / latest run id / pending status), status meta card,
  run history mini-timeline, raw markdown source viewer (read-only with
  'Edit via i2e-intent' footer).
- Pending view (`/pending`): watcher summary chips, Human evaluations
  section, Escalations section, per-pending card with ask / attempts /
  expect / observed / resolve button, resolve dialog (verdict options +
  notes textarea + Write button).
- `POST /api/intents/<slug>/promote`: runs `intent_authoring.validate_intent`
  first; 422 with structured errors on invalid; calls
  `intent_authoring.promote_intent` on valid; returns updated fragment.
- `POST /api/pending/<file>/resolve`: body { verdict, notes }; writes
  `resolution:` block; returns updated card; UI shows
  'queued, applied on next tick'.
- Promote validation modal: surfaces structured errors
  (`{field, msg}` list); Promote stays disabled via `hx-disabled-elt`
  until fixed via `i2e-intent`.

## Evidence of success

- id: intent-view-split-layout
  type: case
  provider: pytest
  query: tests/console/test_intent_view.py::test_renders_split_layout
  expect: passes
  effort: medium

- id: intent-view-promote-validates
  type: case
  provider: pytest
  query: tests/console/test_intent_view.py::test_promote_button_validates
  expect: passes
  effort: medium

- id: resolve-writes-resolution-block
  type: case
  provider: pytest
  query: tests/console/test_pending.py::test_resolve_writes_resolution_block
  expect: passes
  effort: medium

- id: resolve-visible-to-adapt
  type: case
  provider: pytest
  query: tests/console/test_pending.py::test_resolve_visible_to_adapt_skill
  expect: passes
  effort: medium

- id: promote-blocks-invalid
  type: case
  provider: pytest
  query: tests/console/test_promote.py::test_blocks_invalid_intent
  expect: passes
  effort: medium

- id: promote-allows-valid
  type: case
  provider: pytest
  query: tests/console/test_promote.py::test_allows_valid_intent
  expect: passes
  effort: medium

- id: boundary-status-field-only
  type: case
  provider: pytest
  query: tests/console/test_boundaries.py::test_console_only_writes_status_field
  expect: passes
  effort: medium

- id: boundary-resolution-block-only
  type: case
  provider: pytest
  query: tests/console/test_boundaries.py::test_console_only_writes_resolution_block
  expect: passes
  effort: medium

- id: promote-modal-blocks-invalid
  type: target
  provider: human
  query: Take a draft intent that fails validation (e.g. missing watcher or evidence). Try to promote it in the console. Does the modal show the right errors and prevent the status change?
  expect: yes — modal lists each field+msg error and the intent status stays draft on disk
  effort: low

- id: pending-resolution-applied-by-adapt
  type: target
  provider: human
  query: Resolve a pending in the UI (verdict + notes). Run /i2e. Does i2e-adapt apply the resolution and clear the pending file as expected?
  expect: yes — after the next i2e tick the pending file is gone and the verdict shows on the intent
  effort: low

## Constraints

- id: no-writes-outside-boundary
  provider: pytest
  query: tests/console/test_security.py::test_no_writes_outside_boundary
  expect: passes
  effort: medium
