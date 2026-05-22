---
capability: visual-review-pending-fields
created: '2026-05-21'
updated: '2026-05-21'
version: 1
status: shipped
watcher: '@me'
touches:
- src/i2e_core/intent.py
- src/i2e_core/pending.py
- .claude/skills/i2e-provider-human/**
- tests/test_visual_review_pending_fields.py
---

When a human-in-the-loop target is reviewing something visual, the human
needs to know *exactly* what to open and what to look at. Today the
provider only carries `query` (free-form prompt) and `expect` — there's
no structured "URL to open", "steps to follow", or "screenshot to
compare against" surface in the pending file. Reviewers either get a
vague prompt or a wall of instructions stuffed into `query`.

Extend the `EvidenceItem` schema and `PendingFile` schema with three
optional fields targeted at visual review:

- `url` — what to open in the browser (relative or absolute)
- `steps` — ordered list of strings; what the reviewer should do
- `screenshot` — path or URL to a reference image (gitignored uploads
  also fine)

`i2e-provider-human` copies these from the item onto the pending file so
the watcher sees them as discrete fields, not buried inside `ask`. All
three are optional and default to absent — existing intents and pending
files stay valid.

## Evidence of success

- id: evidence-item-accepts-visual-fields
  type: case
  provider: pytest
  query: tests/test_visual_review_pending_fields.py::test_evidence_item_accepts_url_steps_screenshot
  expect: passes
  effort: low

- id: pending-file-carries-visual-fields
  type: case
  provider: pytest
  query: tests/test_visual_review_pending_fields.py::test_pending_file_carries_visual_fields
  expect: passes
  effort: low

- id: human-provider-copies-visual-fields
  type: case
  provider: pytest
  query: tests/test_visual_review_pending_fields.py::test_human_provider_copies_visual_fields_onto_pending
  expect: passes
  effort: low

- id: existing-intents-still-parse
  type: case
  provider: pytest
  query: tests/test_visual_review_pending_fields.py::test_existing_intents_without_visual_fields_still_parse
  expect: passes
  effort: low

- id: visual-target-blocks-shippable-until-resolved
  type: case
  provider: pytest
  query: tests/test_visual_review_pending_fields.py::test_visual_target_blocks_shippable_until_human_resolves
  expect: passes
  effort: medium

## Constraints

- id: visual-fields-are-optional
  provider: pytest
  query: tests/test_visual_review_pending_fields.py::test_visual_fields_default_to_absent
  expect: passes
  effort: low
