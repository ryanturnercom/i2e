---
capability: report-shows-drafts
created: '2026-05-20'
updated: '2026-05-20'
version: 1
status: draft
watcher: '@ryan'
---

# Report shows draft intents in a separate section

The HTML report (`.i2e/report.html`, also served live by `i2e-serve`)
currently lists only `status: active` capabilities — drafts are silently
hidden by `_list_active_capabilities` in `src/i2e_core/report/view_model.py`.
That makes it hard to see what is being authored vs. what is being run.

This capability adds a distinct "Drafts" section to the report:

- `ReportViewModel` grows a `drafts: list[CapabilityView]` field, populated
  from intents whose frontmatter `status == "draft"`.
- The Jinja template (`src/i2e_core/report/templates/report.html.j2`) renders
  drafts under their own heading, visually separated from active capabilities.
- Retired capabilities are still hidden.
- Evidence verdicts for drafts are shown if a `current.yaml` exists, otherwise
  the items render as "no data" (same fallback the active path uses).

Drafts do NOT contribute to the `shippable` flag — only active capabilities
do.

## Evidence of success

- id: draft-caps-in-view-model
  type: case
  provider: pytest
  query: tests/report/test_view_model.py::test_drafts_listed_separately
  expect: passes
  effort: medium

- id: draft-section-in-html
  type: case
  provider: pytest
  query: tests/report/test_render.py::test_html_has_drafts_section
  expect: passes
  effort: medium

- id: active-section-excludes-drafts
  type: case
  provider: pytest
  query: tests/report/test_view_model.py::test_active_capabilities_excludes_drafts
  expect: passes
  effort: low

- id: drafts-do-not-affect-shippable
  type: case
  provider: pytest
  query: tests/report/test_view_model.py::test_shippable_ignores_drafts
  expect: passes
  effort: low

## Constraints

- id: retired-still-hidden
  provider: pytest
  query: tests/report/test_view_model.py::test_retired_capabilities_hidden
  expect: passes
  effort: low
