# Intent-to-Evidence (Simplified)

> A small, agent-native SDLC: humans declare intent, an AI agent builds and
> proves it, evidence is forced, and the loop never ends.

This is the **simplified** form of [I2E](./I2E.md) — same IDEA loop, fewer
moving parts, code in normal places, the whole thing driven by skills.

---

## What changed from I2E v1

| v1 | Simplified |
|---|---|
| Charter with **four sections** (Purpose, Targets, Cases, Constraints) | **One file per Capability** with two lists (Evidence of Success, Constraints) — Cases & Targets are *types of evidence*, not sections |
| **Five named roles** (Charter Owner, Case Librarian, Constraint Keeper, Verifier, Watcher) | No formal roles. Each evidence item names a `watcher`. Team norms govern. |
| Source code under `.i2e/develop/<run-id>/system/` | Source code in **normal `src/`** — `.i2e/` only holds intent, proof, and history |
| 45 skills across 3 tiers | **6 loop skills + N provider skills** |
| Custom SKILL.md schema | [agentskills.io](https://agentskills.io) SKILL.md convention |
| `Delta` proposal artifacts | A `pending/` queue — one file per item waiting on a human |
| Dashboard renders inside the loop | Two skills: `i2e-report` (static, auto on tick) and `i2e-serve` (live, opt-in) |
| Scheduler not addressed | **BYO scheduler** — Claude Code `/schedule` routines or OS scheduler (no CI required) |

---

## 1. Concept — the IDEA loop

Four phases, run forever:

| Phase | What happens | Owner |
|---|---|---|
| **Intent** | Author or edit a Capability file. Declare what should be true and how it will be proven. | Human |
| **Develop** | Build the System in `src/`. AI agent. | AI |
| **Evidence** | Invoke each item's provider skill. Collect proof. | AI |
| **Adapt** | Read evidence; auto-improve within budget; escalate to `pending/` when stuck. | AI (then human) |

The loop is driven by a single **orchestrator skill** (`i2e`) that decides
which phase to run next based on project state.

---

## 2. Artifacts

### 2.1 The Intent file

One file per **Capability** under `.i2e/intents/`. Filename is plain (e.g.
`shorten-url.md`). Dates live in frontmatter, not the filename.

```markdown
---
capability: shorten-url
created: 2026-05-19
updated: 2026-05-19
version: 1
status: active                    # draft | active | retired
watcher: '@platform-team'         # default for every item below
depends_on: []                    # optional; slugs this capability waits on
touches: ['src/shorten_url/**', 'tests/test_shorten_url.py']
                                  # optional; globs develop is allowed to write
---

# Shorten a URL

A user turns a long URL into a short one and is redirected.

## Evidence of success

- id: code-generated
  type: case
  provider: pytest
  query: tests/test_shorten.py::test_returns_7_char_code
  expect: passes
  effort: medium

- id: redirect-latency-p95
  type: target
  provider: datadog
  query: redirect_latency{quantile=0.95}
  window: 5m
  expect: <50ms
  effort: medium

- id: brand-feel
  type: target
  provider: human
  query: |
    Open the shortener and shorten 3 different URLs.
    Does the experience feel trustworthy and snappy?
  expect: yes
  effort: lazy

## Constraints

- id: no-open-redirect
  provider: pytest
  query: tests/adversarial/test_open_redirect_blocked.py
  expect: passes
  effort: high

- id: pii-not-logged
  provider: sentry
  query: events:contains("http") in:logs
  expect: 0
  effort: high
```

Three sections; every item has the **same shape**.

`depends_on:` is an optional list of capability slugs this one must wait on.
When present, preflight rejects unknown references and any cycle, and
`decide()` will not advance a child capability while a parent is still in
the develop-needed set (see §6.1).

`touches:` is an optional list of globs describing the file paths
`i2e-develop` is allowed to write for this Capability. When omitted, it
defaults to `['**']` — the legacy "may write anywhere" behaviour. A
post-develop check fails the tick if any file outside the declared scope
was modified. Two capabilities whose `touches:` globs overlap may not run
in parallel (see §4.1).

`spec:` and `spec_section:` are optional frontmatter fields populated by
the `i2e-spec` skill (§4.1) when a capability is decomposed from a PRD.
`spec:` is the slug of the source spec under `.i2e/specs/`; `spec_section:`
is the 1-based section index. Together they let `i2e-spec --reconcile`
diff the on-disk spec against the intents that claim it and propose
add/edit/retire pending files.

### 2.2 Case vs. Target — the deciding test

> **Can the agent get a verdict right now, from the system alone?**

| | **Case** | **Target** |
|---|---|---|
| Evidence is | Generated immediately, programmatically | Observed — needs time, a 3rd-party provider, or a human subject |
| The agent... | Executes it; gets pass/fail now | Waits for it; reads a result later |
| Examples | unit test, API probe, schema check, lint | Datadog usage trend, Sentry error rate, NPS, user interview |
| Role in loop | **Gates the ship** at build time | **Measured after ship**, feeds Adapt |
| Provider returns | `pass` / `fail` | a value vs. `threshold` → `met` / `unmet` / `trending` |

**Constraints** use the same item shape; they're invariants ("never X")
rather than success criteria. They gate the ship too.

### 2.3 Effort tiers

Every item carries an `effort` tier that bounds the auto-improvement budget.
Tiers are defined in `.i2e/config.yaml`; Cases get bigger budgets than
Targets because each case loop is seconds while each target loop can be
weeks.

```yaml
# .i2e/config.yaml
effort_tiers:
  case:
    lazy:   { max_attempts: 0 }    # fails -> escalate to human, no auto-retry
    low:    { max_attempts: 3 }
    medium: { max_attempts: 6 }
    high:   { max_attempts: 10 }
  target:
    lazy:   { max_attempts: 0 }
    low:    { max_attempts: 1 }
    medium: { max_attempts: 3 }
    high:   { max_attempts: 5 }

defaults:
  case_effort: medium
  target_effort: low
  watcher: '@me'

scheduler:                         # advisory only
  cadence: weekly
  via: claude-code-routine         # or windows-task-scheduler | launchd | cron | manual
```

`lazy` is the explicit "don't auto-loop" escape hatch — useful when you'd
rather have a human decide than have the AI thrash.

---

## 3. Repository layout

```
<project-root>/
├── src/                  source code, normal place, nothing special
├── tests/                normal test layout
├── .i2e/
│   ├── context/          standing reference docs — DESIGN.md, ARCHITECTURE.md...
│   ├── specs/            preserved source PRDs/design docs decomposed via `i2e-spec`
│   ├── intents/          one file per Capability
│   ├── evidence/
│   │   └── <capability>/
│   │       ├── current.yaml      always-rewritten; latest verdict per item
│   │       └── runs/
│   │           └── <run-id>.yaml immutable per-run snapshot
│   ├── pending/          items awaiting human input (open | resolved)
│   ├── logs/             append-only archive of resolved pending + non-empty ticks
│   ├── report.html       static dashboard, regenerated on every state change
│   └── config.yaml       effort tiers, defaults, advisory scheduler
```

`.i2e/context/` is **not loop-driven**. It's standing reference (architecture
notes, glossary, conventions) the agent *reads* during Develop but never
has to "prove."

---

## 4. Skills

Two families: **loop skills** that drive IDEA, and **provider skills** that
collect evidence. All follow the agentskills.io SKILL.md convention.

### 4.1 Loop skills

| Skill | Purpose |
|---|---|
| `i2e` | Orchestrator. Runs a preflight scan and advances the project by one step. |
| `i2e-intent` | Author or edit Capability files. Only skill that touches `draft` intents. |
| `i2e-spec` | Bulk decomposer: a PRD or design doc -> N draft capability files under `.i2e/intents/`, with the source preserved under `.i2e/specs/<slug>.md`. `--reconcile <slug>` diffs an edited spec against the intents that claim it. |
| `i2e-develop` | Build the System in `src/`. Reads `.i2e/context/` for standing reference. Honours `touches:` — writes outside the declared globs fail the tick. Fans out within a capability: a `plan_develop` step groups evidence items by target file and runs distinct files in parallel sub-agents (one batch per same-file depth), so a capability that touches three independent files lands in roughly the time of the slowest. |
| `i2e-evidence` | For each item, invoke its provider skill; write `current.yaml` + a new `runs/<id>.yaml`. |
| `i2e-adapt` | Read evidence; auto-revise + re-trigger Develop within budget; on exhaustion, write to `pending/`. |
| `i2e-report` | Render `.i2e/report.html` from current state. Auto-called by `i2e` after any state-changing tick. Deterministic Python, zero LLM tokens. |
| `i2e-serve` | Optional. Start a tiny localhost HTTP server (127.0.0.1 only) with live SSE updates from `.i2e/` file changes. |

### 4.2 Provider skills

One skill per evidence source. Naming convention: `i2e-provider-<name>`.
Examples: `i2e-provider-pytest`, `i2e-provider-datadog`,
`i2e-provider-sentry`, `i2e-provider-ga`, `i2e-provider-human`,
`i2e-provider-survey`.

Each provider skill takes one evidence item and returns a verdict:

- For a Case: `{ verdict: pass | fail, output: "..." }`
- For a Target: `{ value: <observed>, met: true | false | trending, observed_at: <iso> }`
- For a Constraint: same shape as a Case.

**The installed skill set IS the provider registry.** To add Sentry, you
install `i2e-provider-sentry`. No central config file.

---

## 5. Enforcement — forced-evidence rules

Validation runs on every intent edit (in `i2e-intent`) and on every
orchestrator tick (in `i2e`'s preflight). A Capability is **invalid** if:

1. Any evidence item omits `provider`.
2. Any evidence item names a provider with no matching installed
   `i2e-provider-*` skill. *You cannot declare evidence you have no way to
   collect.*
3. The Capability has zero evidence items. *Every intent has at least one
   way to know it worked.*
4. The `depends_on:` graph across all active intents must be acyclic and
   every referenced slug must exist as an active capability. *You cannot
   depend on something that isn't real, and a cycle would deadlock the
   loop.*

There are no other "ceremony" gates. Shipping is gated by **all Cases pass
and all Constraints hold** in the latest `current.yaml`. Targets do not
gate shipping — they feed Adapt after the fact.

---

## 6. The cyclic process

### 6.1 Orchestrator decision tree

When `i2e` is invoked, it runs a preflight scan and takes the **first**
action that applies:

```
1. Any pending/ file with status: resolved?
   → apply the human's resolution to the intent file, archive to logs/

2. Any active intent file with no matching evidence (new or version-bumped)?
   → i2e-develop, then i2e-evidence on that Capability.
   `depends_on:` is respected: among the set of capabilities that need
   develop, a child whose parent is also in the set is held back; the
   alphabetical tiebreaker applies only inside the *ready* set.

3. Any current.yaml showing trending/unmet items with budget remaining?
   → i2e-adapt → another i2e-develop + i2e-evidence cycle

4. Any target whose window has elapsed since last_observed?
   → i2e-evidence re-evaluates just that item

5. All Capabilities have current.yaml all met/pass?
   → mark shippable; do nothing.
```

After any step that changes state, `i2e-report` runs and `.i2e/report.html`
is refreshed.

### 6.2 Pending — the human-in-the-loop queue

When `i2e-adapt` exhausts an item's budget — or when an async provider
(`i2e-provider-human`, `i2e-provider-survey`) needs a first-time verdict —
a file is written to `.i2e/pending/`:

```yaml
# .i2e/pending/2026-05-19-shorten-url-usage-growth.yaml
status: open                       # open | resolved
kind: escalation                   # escalation | human_evaluation
capability: shorten-url
item_id: usage-growth
escalated_at: 2026-05-19T14:32:00Z
reason: max_attempts exhausted (3/3) without meeting threshold
expect: "+10% QoQ"
observed: "+2.1% QoQ over 3 weeks"

attempts:
  - run_id: 2026-04-29-aaa111
    changed: added share-to-twitter button
    observed: "+0.8% in 1 week"
  - run_id: 2026-05-06-bbb222
    changed: prominent CTA on homepage
    observed: "+1.5% in 1 week"
  - run_id: 2026-05-13-ccc333
    changed: reduced redirect latency
    observed: "+2.1% in 1 week"

ask: |
  Three improvement loops tried — usage is growing but slower than +10% QoQ.
  Pick one:
    1. Loosen the target (e.g. "+5% QoQ" — the trend is positive)
    2. Try a new approach (describe)
    3. Retire this target (no longer the right measure)
    4. Accept current state as "met" and continue

resolution:                        # human fills this in
```

The human edits the file directly (or uses the dashboard), writes a
`resolution:` block, sets `status: resolved`. On the next tick the
orchestrator applies the resolution to the intent file, then **moves the
pending file to `logs/`**. `pending/` shows only live items.

### 6.3 Scheduler — BYO

I2E ships no scheduler. The orchestrator is just a skill; anything that
can invoke an agent on a cadence works. Recommended patterns:

- **AI coding agent native** — Claude Code `/schedule` routines, invoked
  from `i2e` itself on first run. Zero infrastructure.
- **OS scheduler** — Windows Task Scheduler, macOS launchd, cron:
  ```
  claude -p "Run i2e" --cwd <project-path>
  ```

The doc explicitly does not recommend CI-based scheduling or serverless
cron — they introduce hosting dependencies I2E doesn't need.

---

## 7. Evidence format

```
.i2e/evidence/shorten-url/
├── current.yaml                   latest verdict per item
└── runs/
    ├── 2026-05-19-a3f8c2.yaml
    ├── 2026-05-12-b9e1d0.yaml
    └── 2026-04-29-c2a445.yaml
```

`current.yaml`:

```yaml
capability: shorten-url
last_run: 2026-05-19-a3f8c2
intent_version: 1

items:
  code-generated:
    verdict: pass
    last_observed: 2026-05-19T14:32:00Z
  redirect-latency-p95:
    verdict: met
    value: "32ms"
    last_observed: 2026-05-19T14:32:00Z
  brand-feel:
    verdict: awaiting_human
    pending: 2026-05-19-shorten-url-brand-feel
  usage-growth:
    verdict: trending
    value: "+2.1% over 3 weeks"
    attempts_used: 3
    last_observed: 2026-05-19T14:32:00Z
```

A per-run snapshot (`runs/<run-id>.yaml`) includes the full item list with
verdicts, the `intent_version`, the `collected_at` timestamp, and any
provider raw output. `i2e-adapt` diffs the last two runs for any target to
detect trend direction.

---

## 8. Dashboard / report

Two skills, one renderer, same templates:

- **`i2e-report`** — writes `.i2e/report.html` from current state.
  Auto-invoked by the orchestrator at the end of any state-changing tick.
  Deterministic Python; **zero LLM tokens**. Always fresh as of the last
  tick. Shared as a `file://` link.
- **`i2e-serve`** — optional. Starts a detached localhost HTTP server
  bound to 127.0.0.1, with SSE pushes on `.i2e/` mtime changes. Started
  manually when actively working; killed when done.

### Deep links

Agents share fragments into the report so the user lands directly on the
relevant item:

| Fragment | Lands on |
|---|---|
| `#cap/<capability>` | That Capability's card |
| `#item/<capability>/<id>` | That specific evidence item |
| `#pending/<filename>` | That pending file with its resolution template |
| `#tick/<tick-id>` | That tick log entry |

The agent picks `http://localhost:<port>/...` if `.i2e/.serve.url` exists
(server is up), otherwise `file:///.../.i2e/report.html#...`. Same
fragment scheme either way.

---

## 9. Logs

Append-only, dated, signal-only — empty ticks don't log.

```
.i2e/logs/
├── 2026-05-19-shorten-url-usage-growth.yaml   archived pending (one per resolution)
└── 2026-05-19-a3f8c2-tick.yaml                 orchestrator tick that did something
```

Tick log shape:

```yaml
tick_id: 2026-05-19-a3f8c2
ran_at: 2026-05-19T14:32:00Z
actions:
  - applied_resolution: shorten-url / usage-growth
  - ran_develop: shorten-url (intent v1 -> v2)
  - ran_evidence: shorten-url (1 pass, 1 trending)
```

---

## 10. Worked example — bug becomes a Case

A user reports: *"A 3-space password is accepted."*

**Add the case** (and the constraint that should have prevented it) under
`.i2e/intents/change-password.md`:

```yaml
- id: short-password-rejected
  type: case
  provider: pytest
  query: tests/edge/test_short_password_rejected.py
  expect: passes
  effort: medium

- id: whitespace-only-rejected
  type: case
  provider: pytest
  query: tests/adversarial/test_whitespace_password_rejected.py
  expect: passes
  effort: medium

## Constraints
- id: password-min-length-8
  provider: pytest
  query: tests/constraints/test_password_min_length.py
  expect: passes
  effort: high
```

Bump `version` and `updated` in frontmatter. Run `i2e`:

1. Orchestrator sees the version bump → invokes `i2e-develop` → AI
   tightens the password validator.
2. `i2e-evidence` invokes `i2e-provider-pytest` for each new item and the
   existing items.
3. All Cases + Constraints pass → `current.yaml` reads green → shippable.

The bug **cannot recur** — those three items run on every future
development. The cases are version-controlled, the fix is permanent.

---

## 11. Principles

1. **Code is an output, not the artifact.** Intents are the artifact. Code
   regenerates from them.
2. **Forced evidence.** Every claim of "it works" has a named provider
   that proves it. No aspirational metrics.
3. **The agent does the work; the human steers.** Pending is the only
   queue humans look at to know what they owe the loop.
4. **Cases beat specs.** Concrete scenarios are more honest than abstract
   rules.
5. **The loop never ends.** Targets that come back unmet feed the next
   loop. Bugs become Cases that gate every future build.
6. **Minimum infrastructure.** No daemon, no CI dependency, no central
   config beyond `.i2e/config.yaml`. The installed skill set is the
   capability of the system.
7. **Tokens are precious.** Anything deterministic (rendering, file
   writes, validation) lives in Python scripts, not LLM reasoning.
8. **Declared file scope > inferred.** A Capability's `touches:` globs are
   the source of truth for what develop may write. Parallel scheduling and
   the post-develop check both rely on this — never infer scope from
   accidental write history.
9. **Parallelize within capability when files are independent.** A
   Capability that touches multiple independent files runs one sub-agent
   per file in parallel; same-file goals serialize. Single-file
   capabilities skip the fan-out and run as one direct write — no overhead.

---

## 12. Planned extensions (v2 design)

The sections above describe the system as it ships today. Five staged
intents (all `status: draft` until reviewed) propose a v2 design that
addresses four gaps: PRD ingestion, dependency ordering, multi-capability
parallelism, and within-capability fan-out.

Each item below links to a draft intent under `.i2e/intents/`. None has
been activated; this section will be folded into the relevant numbered
sections above as each intent reaches `shippable`.

### 12.1 Capability dependencies — `depends_on:`
Intent: [`intent-depends-on-field`](../.i2e/intents/intent-depends-on-field.md)

Add `depends_on: [slug, ...]` to capability frontmatter. Preflight rejects
cycles and unknown references. `decide()` topologically sorts the eligible
set before the existing alphabetical tiebreaker, so a child never fires
before its parent reaches `shippable`. Lands changes in §2.1, §5, §6.1.

### 12.2 Declared file scope — `touches:`
Intent: [`intent-touches-field`](../.i2e/intents/intent-touches-field.md)

Add `touches: [glob, ...]` to capability frontmatter. `i2e-develop` may
not write outside the declared globs (post-develop check). Two capabilities
with overlapping `touches:` cannot run in parallel — the swarm scheduler
serializes them. Lands changes in §2.1, §4.1, and adds a principle in §11.

### 12.3 Swarm tick — one batch per tick
Intent: [`swarm-tick`](../.i2e/intents/swarm-tick.md)

Replaces "one action per tick" with "one batch of non-conflicting actions
per tick." Builds on 12.1 and 12.2. Algorithm: compute eligible set →
topo-sort by `depends_on:` → greedy-select a batch with no `touches:`
overlap → claim each capability by atomically creating its
`.i2e/worktrees/<slug>/` directory → dispatch develop + evidence in
parallel via the Agent tool's `isolation: worktree` → merge results back
deterministically.

**Concurrency primitive — worktree directory as claim**

There are no hidden `.lock` sidecar files. A capability is "claimed" iff
`.i2e/worktrees/<slug>/` exists, and the atomic primitive is
`os.makedirs(path, exist_ok=False)` (CAS on directory existence; atomic on
both POSIX and Windows). Inside the worktree, `claim.json` records
`{pid, tick_id, started_at}` for liveness checks. A dead PID means a
stale claim — the next tick removes the worktree and reclaims.

Frontmatter `status:` remains intent state (`draft`/`active`/`retired`)
and is never touched by the tick. After a successful claim, the
orchestrator *mirrors* a minimal `runtime:` block into the intent
frontmatter (agent_id, session_id, tick_id, step, started_at, worktree)
for at-a-glance visibility — `grep -l "^runtime:" .i2e/intents/*.md`
shows what's running. The mirror is removed on release. `claim.json`
remains authoritative; deleting the `runtime:` block by hand does not
release the lock — only removing the worktree (or stale-PID sweep) does.
The orchestrator gets a narrow carve-out to write the `runtime:` block
only; `i2e-intent` still owns the rest of the frontmatter.

No global lock is required at the orchestrator level: two concurrent ticks
are safe as long as they claim disjoint capabilities. Lands changes in §2.1,
§3, §6.1, §8, §9, §11.

### 12.4 PRD → intents — `i2e-spec` skill
Intent: [`i2e-spec-skill`](../.i2e/intents/i2e-spec-skill.md)

New loop skill that ingests a markdown PRD or design doc and decomposes
it into N draft intent files with `depends_on:` and `touches:` populated
from the spec's structure. Preserves the original at `.i2e/specs/<slug>.md`.
Each generated intent's frontmatter links back: `spec: <slug>`,
`spec_section: <ref>`. A `--reconcile` subcommand keeps the intents and
the source spec in sync over time. Lands changes in §2.1, §3, §4.1, and
Appendix B.

### 12.5 Within-capability fan-out — parallel develop
Intent: [`develop-parallel-fanout`](../.i2e/intents/develop-parallel-fanout.md)

`i2e-develop` plans a file-level task list and spawns one Agent per
independent file in parallel (Claude Code's Agent tool already supports
this). Goals sharing a file run sequentially. Requires 12.2 for the
`touches:` scope. Lands changes in §4.1 and adds a principle in §11.

### 12.6 `shipped` status for completed capabilities
Intent: [`intent-shipped-status`](../.i2e/intents/intent-shipped-status.md)

Adds a fourth status — `shipped` — to the `draft` / `active` / `retired`
trio. Auto-promote `active → shipped` the first tick `current.yaml` is
all-green (every verdict in `{pass, met}`). Shipped capabilities are
skipped by branches 1–3 but branch 4 (target `window:` elapsed) still
applies — if a target re-evaluates to `unmet`/`trending`/`fail` the
orchestrator auto-demotes back to `active`. Case (pytest) regressions
do **not** auto-demote — see 12.7. Status writes happen through the same
narrow orchestrator carve-out used by `runtime:` in 12.3. The report
renders shipped capabilities in their own "Shipped (N)" section. Lands
changes in §2.1, §6.1, §8.

### 12.7 `i2e-regression` skill — periodic case re-validation
Intent: [`i2e-regression`](../.i2e/intents/i2e-regression.md)

Companion to 12.6. The IDEA loop has no mechanism to re-run pytest cases
for shipped capabilities — code rot, dependency upgrades, or external
regressions can silently break them. The `i2e-regression` skill re-runs
all case + constraint evidence for shipped (or active, or all)
capabilities on demand or via cadence. Cases that flip to `fail` demote
the owning capability from `shipped → active`, returning it to the
normal IDEA loop. Targets are explicitly out of scope (they have their
own `window:` mechanism). Cadence is BYO — call directly, schedule via
`/schedule`, or wire to CI. Depends on 12.6. Lands changes in §4.1, §9,
and Appendix B.

### Activation order

The intents are sequenced for safe stepwise rollout:

1. `intent-depends-on-field` (frontmatter only; pure data)
2. `intent-touches-field` (frontmatter only; pure data)
3. `swarm-tick` (orchestrator + worktree machinery + `runtime:` mirror)
4. `intent-shipped-status` (new state + auto-promote/demote)
5. `i2e-spec-skill` (uses 1 + 2 when decomposing)
6. `develop-parallel-fanout` (uses 2 to plan safely)
7. `i2e-regression` (uses 4's demotion path)

Each is independently shippable in this order. Activate one at a time and
let the IDEA loop verify before moving on. 4 can ship before 3 if you
want shipped-status without parallel execution; 7 must come after 4.

---

## Appendix A — Sample provider skill: `i2e-provider-human`

The canonical async provider. Evidence collection is inherently
asynchronous because the agent has to *ask* and *wait*.

```markdown
---
name: i2e-provider-human
description: Collect subjective human acceptance for a Case or Target.
license: Apache-2.0
metadata:
  tier: provider
  version: "1.0.0"
---

# i2e-provider-human

## When to use
Use when an evidence item names `provider: human`. The verdict is a
person's subjective judgment.

## Workflow

1. Read the item's `query` (the prompt for the human) and `expect`
   (the success condition, often `yes`).
2. Write a pending file at `.i2e/pending/<date>-<capability>-<id>.yaml`:
   ```yaml
   status: open
   kind: human_evaluation
   capability: <capability>
   item_id: <id>
   asked_at: <iso-timestamp>
   ask: |
     <item.query>
   verdict_options: [yes, no, partial]
   resolution:
   ```
3. Return a transient verdict: `{ verdict: awaiting_human, pending: <filename> }`.
4. On the next orchestrator tick, the human's `resolution:` will be picked
   up and translated into the real verdict.

## Returns
- `{ verdict: awaiting_human, pending: <filename> }` on first ask
- `{ verdict: pass | fail, resolved_by: <watcher>, resolved_at: <iso> }`
  after the human responds.

## Notes
- This provider pattern (write a pending file, return `awaiting_human`)
  is reusable. `i2e-provider-survey`, `i2e-provider-interview`, and any
  other async-human provider all share this shape — only the
  `verdict_options` and the wording of the `ask:` change.
```

---

## Appendix B — Skill index quick reference

```
i2e                  orchestrator — preflight + one-step advance
i2e-intent           author/edit Capability files
i2e-spec             decompose a PRD into N draft capability files
i2e-develop          build code in src/ from intents
i2e-evidence         invoke providers, write current.yaml + runs/
i2e-adapt            budgeted auto-improvement; pending on exhaustion
i2e-report           render static .i2e/report.html (auto on tick)
i2e-serve            optional localhost server with live SSE updates

i2e-provider-pytest      cases, constraints — test runner
i2e-provider-datadog     targets — metrics, latencies, counts
i2e-provider-sentry      constraints, targets — error rates, PII leaks
i2e-provider-ga          targets — funnel metrics, page events
i2e-provider-human       cases, targets — subjective acceptance
i2e-provider-survey      targets — NPS, satisfaction
i2e-provider-<your>      anything else — one skill per source
```
