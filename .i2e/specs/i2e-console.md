# i2e Console — Web Improvements Spec

> An interactive, locally-served developer console for I2E projects.
> Replaces the single-page static `report.html` with a rich five-section UI
> for managing intents, reviewing evidence, resolving pendings, and
> operating the IDEA loop. Built strictly inside i2e methodology — the
> console observes and triggers, it does not bypass the framework.

This spec describes a multi-epic rebuild of the I2E web surface. The
source design lives in `claude.ai/design` (see `i2e-console/` bundle).
The methodology source of truth remains `.documentation/I2E_simplified.md`
— this document only describes the web layer.

The three capability H2s below decompose into draft intents. Everything
above the first `##` is background; everything that would normally be a
top-level section in the design doc (architecture, methodology contract,
risks, glossary) is collapsed into this preamble so it doesn't generate
spurious draft intents.

---

### Background — What changes

| Today | After this spec |
|---|---|
| Single static `report.html` rendered by `i2e-report` (full state snapshot) | `report.html` becomes a **last-tick summary** (what changed in the most recent tick). Smallest possible artifact. CI-friendly. |
| `i2e-serve` re-renders the same `report.html` on `.i2e/` changes via SSE | `i2e-serve` becomes the **i2e Console** — a multi-route HTMX+Jinja2 app. SSE is still the live-update channel, but now drives targeted fragment swaps. |
| No write endpoints (read-only artifact) | Two narrow write endpoints: **promote draft→active** (validated) and **resolve pending** (writes a `resolution:` block in the shape `i2e-adapt` expects). Plus two LLM-trigger endpoints: **run regression** and **reconcile spec**. |
| No first-class views for specs, evidence, workers, pending | Six top-nav sections: Dashboard, Specs, Evidence, Pending, Workers, Logs. Plus the existing filterable Intents list in the sidebar. |

### Background — Decisions locked in

| Decision | Choice | Why |
|---|---|---|
| **Web tech stack** | HTMX + Jinja2 (server-rendered) | Stays pure-Python; reuses existing `src/i2e_core/report/templates/`; zero Node toolchain; vendors one ~14KB `htmx.min.js`. Bundles cleanly into the Claude plugin / agentskills zip with no build step. |
| **`report.html` scope** | Static last-tick summary only | Tiny artifact for CI / release notes / snapshot. The console is the rich UI. |
| **Write model** | Console writes via `i2e-serve`, calling existing `intent_authoring` for status changes and writing `resolution:` blocks to pending YAMLs for `i2e-adapt` to sweep. No inline intent-source editing. | Honors CLAUDE.md boundary rules; reuses deterministic Python already in the codebase; LLM-heavy edits stay with the `i2e-intent` skill. |
| **Status transitions exposed** | Only `draft → active` (with strict forced-evidence validation). All other transitions remain automatic per methodology. | Tightest methodology fit; minimal blast radius. |
| **Phasing** | Three epics: (10) shell + dashboard, (11) intent + pending + writes, (12) workers + logs + specs + evidence + tweaks + regression. | Each slice ships independently. |
| **Default layout** | Designer's defaults: relaxed density, sidebar grouped by status, cockpit dashboard, split intent-detail. | Matches the prototype 1:1 in epics 10–11; the tweaks panel arrives in epic 12. |
| **Workers view** | Read-only, with live log tail of worker stdout. | Worker lifecycle stays with the orchestrator; the console is an observer. |
| **Specs section** | Browse + 'Reconcile with spec' action (LLM invocation). | Mirrors the regression pattern: a single console-triggered LLM op. |
| **Evidence section** | Tabbed: Catalogue (default) + Runs. | Cross-capability lens for triage and temporal drift-spotting. |
| **Regression UI** | Two triggers — global "Run regression on all shipped" + per-capability "Re-validate this." | Methodology-tight; auto-demotes shipped→active on flip per `i2e-regression`. |
| **Live progress UI** | Toast overlay (sticky bottom-right), persistent record in Logs. | Smallest live surface; reuses Logs as the canonical audit trail. |
| **URL routing** | Clean paths: `/`, `/specs`, `/specs/<id>`, `/evidence`, `/pending`, `/workers`, `/logs`, `/intent/<slug>`. | Bookmarkable; back/forward works. |
| **Tweaks persistence** | Cookie (`i2e_console_prefs`), server-aware so Jinja can render the right variant. | HTMX is server-driven; cookies travel with every request. |
| **Logs default view** | Timeline (matches prototype), with table toggle. | |
| **Empty state** | Onboarding cards pointing at `i2e-intent`, `i2e-spec` CLI commands. | |
| **Notifications** | Sidebar + topbar pulse only (no browser push in v1). | Browser push lives in the separate `watcher-notifications` intent. |
| **Mobile / responsive** | Desktop-first; graceful degradation only. | Developer tool. |
| **Auth / security** | Bind 127.0.0.1 only (unchanged). No additional auth. | Local-only by design. |

### Background — Architecture

#### Module layout

```
src/i2e_core/
  serve.py                  ← becomes the console HTTP app
  console/                  ← new package, all web code
    __init__.py
    app.py                  ← request handler + route table
    views/                  ← one module per top-nav section
      __init__.py
      dashboard.py
      specs.py
      evidence.py
      pending.py
      workers.py
      logs.py
      intent.py
    actions/                ← write + LLM-trigger endpoints
      __init__.py
      promote.py            ← POST /api/intents/<slug>/promote
      resolve.py            ← POST /api/pending/<file>/resolve
      regression.py         ← POST /api/regression/run
      reconcile.py          ← POST /api/specs/<id>/reconcile
    jobs/                   ← long-running operations
      __init__.py
      registry.py           ← in-memory job tracker (id → status / stream)
      runner.py             ← spawns subprocesses, captures stdout
    sse.py                  ← change broker (extends today's _ChangeBroker)
    prefs.py                ← cookie parsing / writing
    static/                 ← vendored htmx.min.js, css, fonts
    templates/              ← Jinja2 templates (replaces report/templates/)
      _base.html.j2
      _sidebar.html.j2
      _topbar.html.j2
      _toast.html.j2
      dashboard/...
      specs/...
      evidence/...
      pending/...
      workers/...
      logs/...
      intent/...
      fragments/            ← htmx-swap targets
        intent-row.html.j2
        pending-card.html.j2
        worker-card.html.j2
        ticks.html.j2
        ...
  report/                   ← shrunk to last-tick summary
    __init__.py
    last_tick.py            ← view_model + render for the tiny report.html
    templates/
      last_tick.html.j2
```

The current `report/` module shrinks to a single deterministic renderer
for the last-tick summary. Templates that were doing the full state
snapshot move to `console/templates/` and split into per-view files.

#### Request lifecycle

```
browser request → serve.py handler
  → console/app.py route table
    → views/<section>.py renders a Jinja template
      → reads .i2e/ via existing view_model code
      → renders full page OR fragment (htmx headers)
  → response

browser action (click) → htmx POST
  → console/app.py route table
    → actions/<name>.py runs the write
      → may call intent_authoring functions
      → may spawn a Job (regression / reconcile)
    → returns HTML fragment for in-place swap
    → notifies SSE broker

file system change (watchdog)
  → sse.py broker
  → fans out event to subscribed clients
    → client uses event payload to decide what to refresh
```

#### SSE event model

Today the broker emits a single "something changed" pulse. The console
needs more granularity so htmx can do targeted swaps instead of
full-page reloads.

```
event: change
data: {"kind": "intent",   "slug": "capability-foo"}
data: {"kind": "pending",  "file": "2026-05-21-abc.yaml"}
data: {"kind": "worker",   "slug": "capability-foo"}
data: {"kind": "tick",     "tick_id": "2026-05-21-a8c4f3"}
data: {"kind": "job",      "job_id": "regression-12-shipped"}
```

Clients use `hx-trigger="sse:change"` and a small JS shim that inspects
`data.kind` and triggers the right element refresh:

| `kind` | Refreshes |
|---|---|
| `intent` | The matching sidebar row + (if visible) intent detail |
| `pending` | Pending count badge + pending view list |
| `worker` | Workers strip + workers view |
| `tick` | Recent ticks panel + Logs view |
| `job` | Toast overlay if it's the active job |

#### Cookie-based preferences

```
i2e_console_prefs = {
  "density": "relaxed",
  "sidebar": "grouped",
  "dashboard": "cockpit",
  "intent": "split",
  "logs": "timeline"
}
```

Set with `Path=/; SameSite=Strict; Max-Age=31536000`. Server reads on
every render; the tweaks panel POST `/api/prefs` writes a new cookie.

### Background — Static report.html

After this spec, `report.html` is a **single page** rendered by
`i2e-report` containing only the most recent tick:

```html
<!doctype html>
<html><head>...</head><body>
  <h1>Last tick · 2026-05-21-a8c4f3</h1>
  <div class="meta">develop · 14:23 UTC · 1m 42s</div>

  <h2>Actions (3)</h2>
  <ul>
    <li>capability-foo: develop → evidence</li>
    <li>capability-bar: status active → shipped</li>
    <li>capability-baz: pending opened</li>
  </ul>

  <h2>Verdict changes (2)</h2>
  <ul>
    <li>capability-foo / case-1: — → pass</li>
    <li>capability-bar / target-2: trending → met</li>
  </ul>

  <h2>Opened pendings (1)</h2>
  <ul>
    <li>capability-baz / target-3 (awaiting_human)</li>
  </ul>
</body></html>
```

Deterministic Python, zero LLM tokens. Auto-rendered by the
orchestrator after any state-changing tick. Embeds enough CSS inline
to be self-contained. **Does not** require `i2e-serve` to be useful.

If `.i2e/logs/` is empty, the file says "No ticks yet — run /i2e."

### Background — Methodology contract

The console **may not** bypass i2e methodology. The following invariants
hold for every console action:

1. **No inline intent body editing.** The intent file body and most
   frontmatter fields require LLM judgment and go through the
   `i2e-intent` skill. The console's only frontmatter mutation is the
   `status` field, and only `draft → active`.
2. **Pending resolutions are queued, not applied.** Writing the
   `resolution:` block does **not** mutate the intent; it stages the
   resolution for the next `i2e-adapt` tick. The console UX
   reinforces this with a "queued, applied on next tick" message.
3. **Regression auto-demotes.** Per `i2e-regression`, any case /
   constraint flip to `fail` / `unmet` / `trending` on a shipped
   capability demotes it to active. The console surfaces this
   prominently in the regression-completion toast.
4. **Auto-ship stays with the orchestrator.** Active → shipped is not
   a console action; the orchestrator auto-ships when a capability
   becomes shippable.
5. **Active → retired and shipped → retired are NOT exposed.**
   Retire happens via the `i2e-intent` skill (which has the LLM
   context to evaluate impact). This is a deliberate v1 trade-off
   and the rationale is documented at the call-site.
6. **LLM-trigger actions** (regression, reconcile) shell out to the
   canonical skill. The console does not re-implement skill logic.
7. **The orchestrator continues to own worker lifecycle.** The
   console observes claim.json + log tail; it never spawns, kills, or
   reassigns a worker.

### Background — Open questions and future work

Not in scope for the three epics below; revisit in a future spec.

- **Browser push notifications** — landed in `.i2e/intents/watcher-notifications.md`.
  Probably integrates with the toast component once that intent ships.
- **Spec authoring from UI** (`i2e-spec` on uploaded markdown). Today
  user must run `i2e-spec` via CLI to create a new spec; only the
  reconcile path is in-console.
- **Manual status transitions beyond promote.** No console UI for
  retire, demote-shipped-to-active manual, etc. CLI / `i2e-intent`
  only.
- **Multi-project switcher.** The sidebar shows a project chip but
  the chip is decorative — there's only one project per `.i2e/`.
- **Authentication.** 127.0.0.1 bind is the only protection. If the
  console ever runs non-locally, this needs OIDC or similar.
- **Mobile / tablet.** Not designed for.
- **Tweakable layouts in epics 10–11.** Until the tweaks panel
  arrives in the third epic, the cookie can still be edited manually
  for testing. UI only exposes the panel in that epic.
- **Workers `cancel` action.** Considered, rejected for v1 — the
  orchestrator owns lifecycle. Add later if operators ask.

### Background — Risks

| Risk | Impact | Mitigation |
|---|---|---|
| HTMX server-round-trips feel sluggish for tweaks panel | UX regression vs prototype | Most tweaks are CSS-class-only; only sidebar/dashboard variant changes require a re-render. Use `hx-swap-oob` to update just the body class without re-rendering full content. |
| Job subprocesses leak if serve dies | Resource leak | Track PIDs in `.i2e/jobs/registry.json`; on serve start, sweep stale entries. Reuse existing `worktrees/` stale-claim sweeping logic. |
| Boundary carve-out for `i2e-serve` weakens methodology | Drift over time | Boundary table in CLAUDE.md updated; tests in `test_boundaries.py` enforce the narrow write set. |
| Vendored htmx falls behind upstream | Security/feature drift | Pin to a tag; bump as part of `release` skill when relevant. |
| SSE events overwhelm client on busy projects | Lag | Server already debounces (200ms); per-kind event filtering keeps unrelated updates cheap. |
| Reconcile job creates conflicting drafts | Data corruption | `i2e-spec --reconcile` is idempotent by design; relies on `spec_section` frontmatter to match. |

### Background — Glossary

- **Console** — the new HTMX+Jinja2 interactive UI served by `i2e-serve`.
- **report.html** — the deterministic, static, single-page last-tick
  summary rendered by `i2e-report`.
- **Job** — a console-triggered long-running operation (regression
  run or spec reconcile). Tracked in-memory by `i2e-serve`; final
  result lands in `.i2e/logs/` as a tick entry.
- **Tweaks** — four user-adjustable layout axes (density, sidebar,
  dashboard, intent) persisted as a cookie.
- **Toast** — sticky bottom-right overlay surfacing in-flight Job
  progress.
- **Forced-evidence validation** — the same set of rules the
  `i2e-intent` skill applies on save. The console's promote button
  calls the same validator.

---

## Console foundation

The shell + dashboard slice of the console rebuild. Lays in the HTMX +
Jinja2 chrome, the sidebar, the topbar, the SSE backbone, and the
cockpit dashboard. Shrinks the static `report.html` artifact to a
last-tick summary so the console becomes the canonical rich UI.

This epic introduces **no console write endpoints**. `i2e-serve` keeps
its current write set (only `.i2e/.serve.url`).

#### Scope

- HTMX shell: base template, topbar, sidebar, toast container, footer.
- Sidebar: project switcher (decorative for v1), top nav (Dashboard /
  Specs / Evidence / Pending / Workers / Logs — Specs and Evidence are
  placeholder pages in this epic), filterable Intents list
  (active / drafts / shipped / retired / all + search + sort by
  updated/name + grouped-by-status).
- Dashboard view (cockpit layout only):
  - **Needs You** strip (top, lilac, when pendings > 0)
  - **Shippability strip** (color bar segment per active capability)
  - **Workers strip** (compact, links to Workers view)
  - **Capability cards** grouped by status
  - **Recent ticks** (last 6)
- TopBar: eyebrow + title + live pulse counters + UTC clock.
- SSE live-updates with granular kinds (intent / pending / worker /
  tick / job).
- `report.html` shrinks to **last-tick summary** rendered by
  `i2e-report`.

#### New / changed files

| Path | Change |
|---|---|
| `src/i2e_core/serve.py` | Routes the new console app. Keeps 127.0.0.1 bind + ephemeral port + `.serve.url` lifecycle. |
| `src/i2e_core/console/app.py` | New. Route table. |
| `src/i2e_core/console/views/dashboard.py` | New. |
| `src/i2e_core/console/sse.py` | Refactor of the existing `_ChangeBroker` to emit typed events. |
| `src/i2e_core/console/prefs.py` | New. |
| `src/i2e_core/console/static/htmx.min.js` | Vendored. |
| `src/i2e_core/console/templates/*` | New tree. |
| `src/i2e_core/report/last_tick.py` | Replaces `report/view_model.py` for the static last-tick summary. |
| `src/i2e_core/report/templates/last_tick.html.j2` | Replaces `report.html.j2`. |

#### Acceptance evidence (to be wired up via `i2e-intent`)

Cases (pytest):
- `tests/console/test_routes.py::test_dashboard_renders`
- `tests/console/test_sidebar.py::test_grouped_filter`
- `tests/console/test_sse.py::test_typed_change_events`
- `tests/console/test_last_tick.py::test_renders_when_no_ticks`
- `tests/console/test_last_tick.py::test_renders_summary_of_latest`

Targets (human):
- "Open the console after running `/i2e` — does the dashboard show all
  three strips populated and the recent ticks list?"

Constraints (pytest):
- `tests/console/test_security.py::test_binds_127_0_0_1_only`

Estimate: ~1 week.

## Console intent and writes

The intent detail view, the pending view, and the two narrow write
endpoints that let an operator drive the IDEA loop from the console
without bypassing the methodology.

This epic introduces the first console writes. The carve-out is
**status-field-only for intents** and **resolution-block-only for
pendings**. Any wider edit (body text, frontmatter beyond status,
attempts) still requires the canonical skill. `CLAUDE.md` boundary
table updates accordingly.

#### Scope

- **Intent detail view** (`/intent/<slug>`, split layout):
  - Header (slug, title, status badge, watcher, updated)
  - In-flight workers strip (live)
  - Pending strip (live, lilac)
  - Evidence table — cases / targets / constraints, each row expandable
    to show provider, query, expect, window, attempts used, last
    verdict, latest run id (link), pending status
  - Status meta card (right rail, sticky)
  - Run history mini-timeline (last 8)
  - Raw `.i2e/intents/<slug>.md` source viewer (read-only, "Edit via
    i2e-intent" footer)
- **Pending view** (`/pending`):
  - Watcher summary chips at top
  - Human evaluations section
  - Escalations section
  - Per-pending card with ask, attempts, expect/observed, resolve button
  - **Resolve dialog** — verdict options + notes textarea + Write
    button
- **Write endpoints**:
  - `POST /api/intents/<slug>/promote`
    - Runs `intent_authoring.validate_intent(slug)` first.
    - On invalid: returns 422 with structured errors; renders the
      "Cannot promote" modal with the list of failures.
    - On valid: calls `intent_authoring.promote_intent(slug)` and
      returns the updated intent fragment.
  - `POST /api/pending/<file>/resolve`
    - Body: `verdict`, `notes`.
    - Writes a `resolution:` block to the pending YAML (same shape
      `i2e-adapt.apply_resolutions` reads).
    - Returns updated pending card.
    - Pending stays in `.i2e/pending/` until the next `i2e-adapt`
      tick applies it; UI shows "queued, applied on next tick."

#### Boundary rule changes

`i2e-serve` write set expands narrowly:

| Path | Why |
|---|---|
| `.i2e/intents/<slug>.md` (frontmatter `status` field only) | Calls existing `intent_authoring.promote_intent`. |
| `.i2e/pending/<file>.yaml` (`resolution:` block only) | Same shape `i2e-adapt` writes. |

Documented at both call sites.

#### Promote validation

The Promote button calls a server-side validator that returns:

```json
{ "valid": true }                            // → ok, flip status
{ "valid": false,
  "errors": [
    {"field": "watcher", "msg": "required"},
    {"field": "evidence", "msg": "must have at least one case or target"}
  ] }
```

Errors render in a modal. Promote stays disabled (`hx-disabled-elt`
trick) until the errors are fixed via the `i2e-intent` skill.

#### Acceptance evidence (to be wired up via `i2e-intent`)

Cases (pytest):
- `tests/console/test_intent_view.py::test_renders_split_layout`
- `tests/console/test_intent_view.py::test_promote_button_validates`
- `tests/console/test_pending.py::test_resolve_writes_resolution_block`
- `tests/console/test_pending.py::test_resolve_visible_to_adapt_skill`
- `tests/console/test_promote.py::test_blocks_invalid_intent`
- `tests/console/test_promote.py::test_allows_valid_intent`
- `tests/console/test_boundaries.py::test_console_only_writes_status_field`
- `tests/console/test_boundaries.py::test_console_only_writes_resolution_block`

Targets (human):
- "Take a draft intent that fails validation. Try to promote in the
  console. Does the modal show the right errors and prevent the
  status change?"
- "Resolve a pending in the UI. Run `/i2e`. Does `i2e-adapt`
  apply the resolution as expected?"

Constraints (pytest):
- `tests/console/test_security.py::test_no_writes_outside_boundary`

Estimate: ~1.5 weeks.

## Console workers, logs, specs, evidence

The final slice: the four secondary views (Workers, Logs, Specs,
Evidence), the floating Tweaks panel, and the two LLM-trigger jobs
(regression run, spec reconcile). Together these complete the cockpit:
the operator can browse every artifact the IDEA loop produces and kick
off the canonical skills without leaving the console.

#### Workers view (`/workers`)

- Read-only. Lists every `.i2e/worktrees/<slug>/claim.json`.
- Per worker:
  - `agent_id`, `capability`, `step`, `started_at`, current `progress`
  - **Live log tail** — last N lines of the worker's stdout
- **Requires new infrastructure**: workers must write stdout to
  `.i2e/worktrees/<slug>/log` (rolling, max 5MB). This is a small
  change to `orchestrator.py`'s worktree-dispatch path. Out of scope
  for the earlier epics but called out as a prerequisite for this
  epic.

#### Logs view (`/logs`)

- Timeline mode (default) and table mode (toggle).
- Filters: phase (intent / develop / evidence / adapt), capability
  slug, kind (tick / regression / reconcile).
- Each entry expands to show `sub_actions` and changed verdicts.
- New tick types `regression` and `reconcile` show up here when
  triggered from the console.

#### Specs view (`/specs`, `/specs/<id>`)

- List view: every `.i2e/specs/*.md` with derived-intents count.
- Detail view:
  - Rendered markdown of the spec
  - "Derived intents" panel — every intent whose frontmatter
    references this spec (via `spec` / `spec_section` fields)
  - **Reconcile button** — triggers `i2e-spec --reconcile` as a Job.
  - Last-reconciled timestamp.

#### Evidence view (`/evidence`)

Tabbed:

- **Catalogue (default)**: flat table of every case / target /
  constraint across all capabilities.
  - Columns: capability | type | item id | provider | latest verdict
    | watcher | last run.
  - Filters: type, verdict, provider, watcher.
- **Runs**: chronological feed of every evidence run, newest first.
  Each row links to the underlying `.i2e/evidence/<slug>/runs/<id>.yaml`.

#### Tweaks panel

Floating panel (bottom-right). Four axes:

- Density (dense / relaxed)
- Sidebar (grouped / flat / tree)
- Dashboard (cockpit / arc / inbox)
- Intent detail (single / split)

Plus logs view default (timeline / table). Persisted via
`i2e_console_prefs` cookie.

#### Regression + Reconcile jobs

Both follow the same pattern.

```
POST /api/regression/run
  body: { scope: "all-shipped" | "slug:capability-foo" }
  → spawns subprocess: python -m i2e_core.regression --scope=...
  → registers Job in jobs/registry
  → returns Job id + initial toast HTML

POST /api/specs/<id>/reconcile
  → spawns subprocess: python -m i2e_core.spec --reconcile <id>
  → registers Job
  → returns Job id + initial toast HTML
```

Job stdout streams into a per-job ring buffer; SSE emits
`{"kind": "job", "job_id": "..."}` events on every line. The toast
component subscribes and re-renders. When the job exits, a final
tick entry is written to `.i2e/logs/` (kind = `regression` or
`reconcile`) and the toast moves to a "completed" state with a link
to the Logs view.

**Jobs are not persisted across i2e-serve restarts.** If serve dies
mid-job, the subprocess survives, the result still lands in Logs, but
the toast is gone.

#### Boundary rule changes

| Path | Why |
|---|---|
| `.i2e/jobs/<job-id>.log` (ring buffer files) | New: per-job stdout capture. `i2e-serve` writes; everything else reads. |
| `.i2e/worktrees/<slug>/log` | New: rolling worker stdout. Written by `orchestrator.py` worktree dispatch. |

#### Acceptance evidence (to be wired up via `i2e-intent`)

Cases (pytest):
- `tests/console/test_workers.py::test_renders_claim_json_fields`
- `tests/console/test_workers.py::test_renders_live_log_tail`
- `tests/console/test_logs.py::test_timeline_default`
- `tests/console/test_logs.py::test_table_toggle`
- `tests/console/test_specs.py::test_lists_specs`
- `tests/console/test_specs.py::test_shows_derived_intents`
- `tests/console/test_specs.py::test_reconcile_spawns_job`
- `tests/console/test_evidence.py::test_catalogue_renders_all_items`
- `tests/console/test_evidence.py::test_runs_tab_chronological`
- `tests/console/test_tweaks.py::test_writes_cookie_on_change`
- `tests/console/test_tweaks.py::test_server_renders_variant_from_cookie`
- `tests/console/test_jobs.py::test_regression_writes_tick_on_complete`
- `tests/console/test_jobs.py::test_job_stdout_streams_via_sse`

Targets (human):
- "Run regression on a shipped capability where one of its cases now
  fails. Does the toast show progress, and does the capability get
  demoted to active when it completes?"
- "Reconcile a spec where you've added a new section. Does it create
  a draft for the new section without disturbing existing intents?"
- "Toggle each tweak axis. Does the layout change persist after a
  full page reload?"

Constraints (pytest):
- `tests/console/test_jobs.py::test_jobs_dont_leak_subprocesses`

Estimate: ~1 week.
