# IDEA Loop — Navigation Layout

The goal of this navigation is not to list screens. It is to make the
**IDEA loop the first thing a user understands** about the product. The
nav *is* the loop. If someone reads the menu and doesn't walk away knowing
"this tool runs Intent → Develop → Evidence → Adapt, forever," the nav has
failed.

---

## The loop the nav must teach

```
            ┌───────────────── resolutions ──────────────────┐
            │                                                │
            ▼                                                │
    ① Intent  ──▶  ② Develop  ──▶  ③ Evidence  ──▶  ④ Adapt ──┘
   declare what     agents build     run providers,    retry within
   should be true   the System       collect pass/     budget, or
   and how it's     in src/          fail proof        escalate to
   proven                                              a human
```

Four phases, run forever, driven by one orchestrator. The single most
important property — the one a flat menu destroys — is that **Adapt loops
back to Intent**. Adapt's resolutions edit intent files; Adapt triggers
fresh Develop cycles. It is a cycle, not a pipeline with an end.

---

## Why the current draft isn't landing

The draft nav is a correct *list* but a weak *teacher*:

- **A vertical list reads as four unrelated sections.** Nothing says
  "these are stages of one cycle." There is no sequence, no return arrow,
  no sense of motion.
- **"Design/Develop" breaks the acronym.** The spec phase is **Develop**.
  The slash and the extra word make a reader stop and re-derive IDEA
  instead of reading it. Every loop label must start with its letter and
  nothing else: **I**ntent · **D**evelop · **E**vidence · **A**dapt.
- **Adapt looks like a dead end.** "Show all failed items" frames Adapt as
  a graveyard. It's the opposite — Adapt is the engine that pushes work
  *back into* Intent and Develop.
- **Overview is mixed in with the stages.** It isn't a stage; it's the
  view *of* all four. Listing it inline flattens the distinction.

---

## The navigation

Overview sits **above** the loop — a separate group, visually divided. The
four loop items sit **inside** a labelled "IDEA loop" group, numbered, in
order, and never reordered or alphabetised.

| Nav item | Letter | Spec phase | What it shows | Owner |
|---|---|---|---|---|
| **Overview** | — | (cockpit) | Dashboard — all four stages at a glance, recent ticks, shippability. Not a stage. | — |
| **Intents** | **I** | Intent | New-intent authoring with search + filters; **Specs** as a sub-tab. The loop *starts* here — and *returns* here when Adapt applies a resolution. | Human |
| **Develop** | **D** | Develop | Workers — agents building the System in `src/`, in-flight, with live step + progress. | AI |
| **Evidence** | **E** | Evidence | Recent runs by capability / case with unambiguous pass/fail. Three sub-tabs: **Runs**, **Automated Targets**, **Human Targets** (see below). | AI |
| **Adapt** | **A** | Adapt | Non-passing items (`fail` / `unmet` / `trending`), each with its retry-budget meter and attempt history — and an explicit **→ back to Intent** path. | AI → Human |

Renamed from the current nav: `Dashboard → Overview`, `Workers → Develop`.
`Logs` becomes **Ticks** — pinned at the bottom as a utility item below the
loop group (see *Mapping*, below). `Pending` does not survive as a
standalone item: it splits by kind into `Evidence → Human Targets` and
`Adapt → Escalations`, each owned by the stage that produces it.

---

## How the UI hammers the loop home

Naming and ordering alone won't do it. The loop has to be *felt*:

1. **Show the letters.** Render `I D E A` as the actual nav — the first
   letter of each label emphasised (weight or colour), or a literal
   I/D/E/A badge per item. The acronym should be impossible to miss.

2. **Number the stages.** `① Intent  ② Develop  ③ Evidence  ④ Adapt`.
   Numbers assert sequence; a bare list does not.

3. **Draw the return.** A connecting line down the four items, and a
   curved arrow from Adapt back up to Intent. The cycle must be visible in
   the chrome, not just implied by the words.

4. **Make the nav a live instrument.** Each loop item carries a count
   badge — drafts waiting in Intents, workers in flight in Develop,
   pending verdicts in Evidence (the `(4)`), failing items in Adapt. A
   user watching the badges *sees the work move around the loop*. That is
   the single strongest "this is a cycle" signal available.

5. **Highlight the active stage.** When the orchestrator is mid-tick,
   pulse or highlight the loop item whose phase is running. The nav
   becomes a status display: "right now we are in Develop."

6. **Every screen points to the next stage.** An Intent screen leads to
   Develop. An Evidence failure leads to Adapt. An Adapt resolution leads
   back to Intent. No loop screen should be a cul-de-sac.

---

## Mapping existing functionality into the flow

Every screen the console has today belongs to exactly one loop stage. The
stage is the primary nav item; the rows beneath it are **sub-tabs within
that stage's screen**, not new top-level entries. The primary nav stays
four loop items. The **Status** column is the build map — what to reuse
versus what is new.

### I · Intent
| Sub-tab | Existing functionality | Status |
|---|---|---|
| **Specs** | `/specs` list + `/specs/<id>` detail. `i2e-spec` decomposes a spec into capabilities; the Reconcile action is already wired. | exists |
| **Capabilities** | The intent files — today scattered across the sidebar's grouped/searchable list, the dashboard's capability cards, and `/intent/<slug>` detail (Promote / Demote). | exists, scattered |

Order mirrors authoring: a Spec is decomposed *into* Capabilities.
Authoring a *new* intent still belongs to the `i2e-intent` skill (boundary
rule — only `i2e-intent` writes `.i2e/intents/**`). A console "new intent"
screen would extend the authoring API the Promote / Demote buttons already
call: new work, not a remap.

### D · Develop
| Sub-tab | Existing functionality | Status |
|---|---|---|
| **Workers** | `/workers` — in-flight `i2e-develop` agents with live step + progress. | exists |

Develop is intentionally **thin**: building `src/` is agent work with one
human-facing artifact — who is working on what, right now. Don't add
filler sub-tabs to balance the tree.

### E · Evidence
| Sub-tab | Existing functionality | Status |
|---|---|---|
| **Runs** | The "Runs" tab already built in `views/evidence.py` — chronological feed of every evidence run, newest first. Each Case verdict is a run. | built, **unrouted** |
| **Automated Targets** | Targets whose verdict comes from an automated provider (`datadog` / `ga` / `sentry`). Today inside the `evidence.py` Catalogue tab and per-capability on `/intent/<slug>`. As a sub-tab: the standing-measurement lens — sorted by window status, with trend lines. Self-refreshing. | partial |
| **Human Targets** | Targets scored by a human provider (`i2e-provider-human` / `i2e-provider-survey`) — the `human_evaluation` half of today's `/pending` screen, awaiting a *first* verdict. The inline resolve form already exists. | exists (in `/pending`) |

`views/evidence.py` exists (Catalogue + Runs tabs) but **has no route** in
`app.py` — wiring Evidence up is mostly routing, not new rendering.

The Targets split is by **verdict source** — the axis that matters:
**Automated Targets** refresh themselves on a schedule; **Human Targets**
sit idle until the operator enters a verdict. The tab itself answers "does
this need me?", and it gives each stage its own human queue instead of one
cross-stage inbox. The framework keeps the split clean: a human/subjective
provider may only serve a `type: target` item — forced at intent-validation
time — so "Human Targets" is exact. There is no such thing as a human Case.

### A · Adapt
| Sub-tab | Existing functionality | Status |
|---|---|---|
| **Off-track** | Every non-passing item (`fail` / `unmet` / `trending`) across all capabilities, each with its retry-budget meter and attempt history. Hosts the "Run regression" trigger — regression's job is surfacing what regressed. | **new screen** |
| **Escalations** | The `escalation` half of today's `/pending` screen — items whose auto-retry budget is spent, each with a 4-option `ask:`. Resolved escalations apply on the next tick. | exists (in `/pending`) |

That answers the `???`. The two sub-tabs are the two faces of Adapt:
**Off-track** is the agent still trying (budget remaining); **Escalations**
is the agent having given up and handed the item to a human. Off-track is
verdict-scoped — a Case from Runs or a Target from either Targets tab appears here
automatically the moment its verdict goes non-passing.

Consequence: the standalone `/pending` screen **dissolves**. Its two
groups become `Evidence → Human Targets` and `Adapt → Escalations`, each
owned by the stage that produces it. No standalone Pending nav item
survives.

### Ticks (Logs)
The bottom utility item — one row per completed IDEA cycle. Reuses the
existing `/logs` screen unchanged; only the route (`/logs → /ticks`) and
label (`Logs → Ticks`) are renamed.

---

## The shape, in one view

```
Overview
───────────────────  IDEA loop  ───────────────────
① Intent     › Specs · Capabilities
② Develop    › Workers
③ Evidence   › Runs · Automated Targets · Human Targets
④ Adapt      › Off-track · Escalations  ──┐
   └───────────── resolutions ◀───────────┘  (back to ① Intent)
────────────────────────────────────────────────────
Ticks
```

---

## Build order

The Status column sorts the work. Recommended sequence — each step ships
something visible:

1. **Nav shell** — the primary nav (Overview + the numbered I/D/E/A group),
   Ticks pinned at the bottom, route `/logs → /ticks`. Pure chrome; every
   destination screen already exists. Highest visibility, lowest cost — and
   it is the whole point of this doc.
2. **Wire Evidence** — give `views/evidence.py` a route. Runs is already
   built; Automated Targets is the Catalogue filtered to automated
   providers. Mostly routing, not new rendering.
3. **Split `/pending`** — move its two groups to `Evidence → Human Targets`
   and `Adapt → Escalations`; retire the standalone screen.
4. **Build Adapt › Off-track** — the one genuinely new screen: non-passing
   items with budget meters + attempt history, plus the regression trigger.
5. **Intent sub-tabs** — Specs is already routed; give Capabilities a
   first-class tab. A console new-intent authoring screen is optional later
   work — new, and boundary-sensitive (only `i2e-intent` writes intents).