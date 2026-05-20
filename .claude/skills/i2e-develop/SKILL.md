---
name: i2e-develop
description: Build the System in src/ from the current active intents. Reads .i2e/context/ for standing reference; writes only to src/ and tests/. Never touches .i2e/.
license: Apache-2.0
metadata:
  tier: loop
  version: "0.1.0"
---

# i2e-develop

The build step of the loop. Given an active Capability whose intent version is
ahead of what the last evidence run knew about, write/update code in `src/` and
tests in `tests/` until the intent's Cases and Constraints are expressible in
code. This skill never runs tests — that's `i2e-evidence`'s job. A clean
separation makes the loop simple to reason about.

## When to use
- Called by the `i2e` orchestrator when an active intent has a higher `version`
  than the last `intent_version` recorded in `.i2e/evidence/<cap>/current.yaml`
- Called by `i2e-adapt` to retry after an evidence failure within budget

## Boundaries
- READ: `.i2e/intents/<cap>.md`, `.i2e/context/*`, `src/**`, `tests/**`,
  `.i2e/evidence/<cap>/current.yaml` (to see prior failure context)
- WRITE: `src/**`, `tests/**` only
- NEVER WRITE: anything under `.i2e/`

## Workflow
1. Resolve the target capability (passed in by orchestrator). If you must
   choose, call `i2e_core.develop.scoped_capabilities(root)` to see which
   active capabilities are stale (intent newer than last evidence).
2. Confirm work is actually needed via `i2e_core.develop.needs_develop(root, cap_name)`.
3. Run `i2e_core.develop.diff_against_current(root, cap_name)` to learn which
   evidence items / constraints are new, changed, or removed since the last
   evidence run, and which items most recently failed (`last_failures`).
4. Discover standing reference docs first — `i2e_core.context.list_context_files(root)`
   and `i2e_core.context.context_summary(root)` give a cheap index. Only then
   call `i2e_core.context.load_context(root)` to read the bodies (it truncates
   at a global character budget to keep the prompt bounded).
5. For each new/changed item, use `i2e_core.develop.suggested_src_paths(cap)`
   and `i2e_core.develop.suggested_test_paths(item)` as defaults — you are
   free to override when the codebase clearly wants something else.
5a. Call `i2e_core.develop.plan_develop(cap)` to fan out across independent
   files. The returned `DevelopPlan.batches` is an ordered list of parallel
   batches: members of one batch target distinct files (run with one
   sub-agent per goal via the Agent tool), and successive batches run
   sequentially. Single-file capabilities collapse to one batch of one
   goal — no parallel-slot overhead. `plan.skipped_out_of_scope` reports
   any goal the planner refused because its path fell outside `touches:`;
   if it's non-empty, fix the intent rather than working around it.
6. Write/update code in `src/` and tests in `tests/` to satisfy every Case and
   every Constraint in the current intent.
7. Do NOT run pytest — that's `i2e-evidence`'s job.
8. Return a summary via `i2e_core.develop.develop_summary(diff, files_touched)`
   so the orchestrator can write it into the tick log.

## Forbidden
- Mocking the provider — let evidence actually run against real adapters
- Editing the intent file — that's `i2e-intent`'s job
- Skipping constraints — they gate ship just like cases
- Writing anywhere under `.i2e/` — that directory is owned by the loop, not by develop
- Running pytest or any other provider — that's `i2e-evidence`'s job

## Python helpers (the deterministic core)
- `i2e_core.develop.needs_develop(root, capability) -> bool`
- `i2e_core.develop.scoped_capabilities(root) -> list[Capability]`
- `i2e_core.develop.diff_against_current(root, capability) -> DevelopDiff`
- `i2e_core.develop.suggested_src_paths(cap) -> list[Path]`
- `i2e_core.develop.suggested_test_paths(item) -> Path | None`
- `i2e_core.develop.develop_summary(diff, files_touched) -> str`
- `i2e_core.develop.plan_develop(cap) -> DevelopPlan`
- `i2e_core.develop.execute_plan(plan, writer, root=None) -> WriteReport`
- `i2e_core.context.list_context_files(root) -> list[Path]`
- `i2e_core.context.load_context(root, max_chars=80_000) -> dict[str, str]`
- `i2e_core.context.context_summary(root) -> str`
