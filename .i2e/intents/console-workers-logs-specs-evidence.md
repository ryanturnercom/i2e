---
capability: console-workers-logs-specs-evidence
created: '2026-05-21'
updated: '2026-05-22'
version: 1
status: shipped
watcher: '@ryan'
depends_on:
- console-intent-and-writes
touches:
- src/i2e_core/console/views/workers.py
- src/i2e_core/console/views/logs.py
- src/i2e_core/console/views/specs.py
- src/i2e_core/console/views/evidence.py
- src/i2e_core/console/actions/regression.py
- src/i2e_core/console/actions/reconcile.py
- src/i2e_core/console/jobs/**
- src/i2e_core/console/templates/workers/**
- src/i2e_core/console/templates/logs/**
- src/i2e_core/console/templates/specs/**
- src/i2e_core/console/templates/evidence/**
- src/i2e_core/console/templates/_toast.html.j2
- src/i2e_core/orchestrator.py
- tests/console/**
- CLAUDE.md
spec: i2e-console
spec_section: '3'
---

The final slice: the four secondary views (Workers, Logs, Specs,
Evidence), the floating Tweaks panel, and the two LLM-trigger jobs
(regression run, spec reconcile). Together these complete the cockpit:
the operator can browse every artifact the IDEA loop produces and kick
off the canonical skills without leaving the console.

Workers view (`/workers`): read-only list of every
`.i2e/worktrees/<slug>/claim.json` with agent_id / capability / step /
started_at / progress and a live log tail of the worker's stdout.
Requires a small change to `orchestrator.py`'s worktree-dispatch path so
workers write stdout to `.i2e/worktrees/<slug>/log` (rolling, max 5MB).

Logs view (`/logs`): timeline (default) and table modes with filters by
phase / capability / kind. Each entry expands to show `sub_actions` and
verdict changes. New `regression` and `reconcile` tick kinds appear
here when triggered from the console.

Specs view (`/specs`, `/specs/<id>`): list every `.i2e/specs/*.md` with
derived-intent counts; detail shows rendered markdown, a Derived intents
panel, a Reconcile button, and the last-reconciled timestamp.

Evidence view (`/evidence`): tabbed Catalogue (default) + Runs.
Catalogue is a flat filterable table of every case / target / constraint
across all capabilities. Runs is a chronological feed linking to the
underlying `.i2e/evidence/<slug>/runs/<id>.yaml`.

Tweaks panel (floating, bottom-right): density / sidebar / dashboard /
intent-detail axes plus logs default. Persisted via
`i2e_console_prefs` cookie.

Regression + Reconcile jobs: `POST /api/regression/run` and
`POST /api/specs/<id>/reconcile` spawn subprocesses, register a Job in
an in-memory registry, stream stdout into a per-job ring buffer at
`.i2e/jobs/<job-id>.log`, and emit `{kind: job, job_id}` SSE events.
On exit a final tick lands in `.i2e/logs/` (kind = regression or
reconcile) and the toast moves to a completed state with a Logs link.
Jobs are not persisted across i2e-serve restarts; the subprocess
survives if serve dies and the result still lands in Logs, but the
toast is gone.

## Evidence of success

- id: workers-renders-claim-fields
  type: case
  provider: pytest
  query: tests/console/test_workers.py::test_renders_claim_json_fields
  expect: passes
  effort: medium

- id: workers-live-log-tail
  type: case
  provider: pytest
  query: tests/console/test_workers.py::test_renders_live_log_tail
  expect: passes
  effort: medium

- id: logs-timeline-default
  type: case
  provider: pytest
  query: tests/console/test_logs.py::test_timeline_default
  expect: passes
  effort: medium

- id: logs-table-toggle
  type: case
  provider: pytest
  query: tests/console/test_logs.py::test_table_toggle
  expect: passes
  effort: medium

- id: specs-lists-specs
  type: case
  provider: pytest
  query: tests/console/test_specs.py::test_lists_specs
  expect: passes
  effort: medium

- id: specs-derived-intents
  type: case
  provider: pytest
  query: tests/console/test_specs.py::test_shows_derived_intents
  expect: passes
  effort: medium

- id: specs-reconcile-spawns-job
  type: case
  provider: pytest
  query: tests/console/test_specs.py::test_reconcile_spawns_job
  expect: passes
  effort: medium

- id: evidence-catalogue-all-items
  type: case
  provider: pytest
  query: tests/console/test_evidence.py::test_catalogue_renders_all_items
  expect: passes
  effort: medium

- id: evidence-runs-chronological
  type: case
  provider: pytest
  query: tests/console/test_evidence.py::test_runs_tab_chronological
  expect: passes
  effort: medium

- id: tweaks-writes-cookie
  type: case
  provider: pytest
  query: tests/console/test_tweaks.py::test_writes_cookie_on_change
  expect: passes
  effort: medium

- id: tweaks-server-reads-cookie
  type: case
  provider: pytest
  query: tests/console/test_tweaks.py::test_server_renders_variant_from_cookie
  expect: passes
  effort: medium

- id: regression-job-writes-tick
  type: case
  provider: pytest
  query: tests/console/test_jobs.py::test_regression_writes_tick_on_complete
  expect: passes
  effort: medium

- id: job-stdout-streams-sse
  type: case
  provider: pytest
  query: tests/console/test_jobs.py::test_job_stdout_streams_via_sse
  expect: passes
  effort: medium

- id: regression-flip-demotes-shipped
  type: target
  provider: human
  query: Run regression on a shipped capability where one of its cases now fails. Does the toast show streaming progress, and does the capability get demoted to active when it completes?
  expect: yes — toast shows live stdout, final tick lands in Logs, capability status flips shipped→active
  effort: low

- id: reconcile-creates-draft-for-new-section
  type: target
  provider: human
  query: Reconcile a spec where you've added a new section. Does it create a draft for the new section without disturbing the existing intents?
  expect: yes — new draft appears under .i2e/intents/ with spec_section set; existing intents unchanged
  effort: low

- id: tweaks-persist-after-reload
  type: target
  provider: human
  query: Toggle each tweak axis (density, sidebar, dashboard, intent-detail, logs default). Does the layout change persist after a full page reload?
  expect: yes — every axis survives a hard reload because the i2e_console_prefs cookie travels with each request
  effort: low

## Constraints

- id: jobs-no-subprocess-leaks
  provider: pytest
  query: tests/console/test_jobs.py::test_jobs_dont_leak_subprocesses
  expect: passes
  effort: medium
