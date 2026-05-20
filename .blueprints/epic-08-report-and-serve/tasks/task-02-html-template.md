# Task: HTML template + deep-link fragments

**Status:** [ ] Pending

**Dependencies:** task-01-report-skill-manifest

## Context

A static, single-file HTML dashboard. No JS frameworks. Inline CSS. Anchor-based deep links (`#cap/<slug>`, `#item/<cap>/<id>`, `#pending/<file>`, `#tick/<id>`). Designed to render identically whether served via `file://` or `http://localhost:<port>/`.

## Needed from User

None.

## Instructions

1. Create `src/i2e_core/report/templates/report.html.j2`:
   - Top: project name + last-tick id + last-tick timestamp
   - Section "Shippable" toggle at top — green pill if all caps green, yellow pill otherwise
   - For each active capability:
     - `<section id="cap/<slug>">` containing:
       - Capability name, intent version, status
       - Item grid: id, type (case/target/constraint), verdict pill, value, attempts_used / max_attempts, last_observed
       - Each item wrapped in `<div id="item/<cap>/<id>">`
   - Pending queue section:
     - For each open pending file: `<details id="pending/<file>">` with `ask:` shown and an inline `<textarea>` showing resolution template
   - Recent ticks section:
     - Last 10 tick logs, each `<article id="tick/<id>">` with actions list
2. Inline CSS at the top — minimal: cards on a light background, color-coded verdict pills (green pass/met, red fail/unmet, amber trending, gray awaiting_human)
3. The template uses no JS. The optional `i2e-serve` injects an SSE listener; the static file doesn't need it.
4. Add a tiny header banner that reads "Served via http://..." or "Opened via file://" depending on whether the template was rendered with `serve_url` context (the renderer reads `.i2e/.serve.url` if present)

## Acceptance Criteria

- [ ] Template renders into valid HTML5 with no JS errors when opened
- [ ] All required deep-link IDs are present (matching the fragment scheme in the spec)
- [ ] Verdict pill colors are correct per verdict
- [ ] Pending queue always shows the resolution textarea (the spec says humans can edit the file OR the dashboard — task-06 will hook the dashboard to write back)
