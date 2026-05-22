---
capability: footer-ryanturner-link
created: '2026-05-20'
updated: '2026-05-21'
version: 1
status: retired
watcher: '@me'
touches:
- src/i2e_core/report/templates/report.html.j2
- tests/report/test_render.py
spec: i2e-web-improvements
spec_section: footer
---

# Report footer references ryanturner.com

The rendered report HTML (`.i2e/report.html`, also served live by
`i2e-serve`) currently ends with `</main>` and a `<script>` block — there
is no footer. Add a small footer that links to **ryanturner.com** so the
report visibly carries the same brand mark as the rest of the
ryanturner.com surface (matches the [[rocksalt-logo-font]] direction).

  - The footer should reference `ryanturner.com` as a clickable link
    (target `https://ryanturner.com`, opens in a new tab).
  - The footer renders on every report — active, drafts, in-flight, all
    states. It is not gated by `shippable`.
  - The footer is part of the static template (no view-model field
    required) so deterministic Python rendering stays trivially correct.

## Evidence of success

- id: footer-link-present
  type: case
  provider: pytest
  query: tests/report/test_render.py::test_footer_links_to_ryanturner
  expect: passes
  effort: low

## Constraints
