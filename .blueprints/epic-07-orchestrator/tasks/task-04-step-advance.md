# Task: One-step advance + report invocation

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-03-decision-tree

## Context

`tick(root)` ties preflight + decide + execute + log + report into the single orchestrator entry point.

## Needed from User

None.

## Instructions

1. Implement `src/i2e_core/orchestrator.py::tick(root) -> TickResult`:
   - `TickResult(BaseModel)`: `tick_id: str`, `action: Action`, `actions_log: list[str]`, `report_path: Path | None`, `shippable: bool`
2. Flow:
   ```
   pre = preflight(root)
   if not pre.valid: raise PreflightFailed(pre)
   tick_id = new_run_id()
   action = decide(root)
   actions_log = []
   if isinstance(action, ApplyResolutions):
       applied = adapt.apply_resolutions(root)
       for a in applied: actions_log.append(f"applied_resolution: {a.capability} / {a.item_id}")
   elif isinstance(action, DevelopAndEvidence):
       # delegate to develop skill (out-of-process LLM call) — for the deterministic side,
       # call evidence_runner.run after the develop step completes
       actions_log.append(f"ran_develop: {action.capability}")  # placeholder; the LLM hook fills detail
       summary = evidence_runner.run(root, action.capability)
       actions_log.append(f"ran_evidence: {action.capability} ({summary.compact()})")
   elif isinstance(action, AdaptThenRetry):
       plan = adapt.plan(root, action.capability)
       actions_log.append(f"ran_adapt: {action.capability} (retries={len(plan.retries)}, escalations={len(plan.escalations)})")
       for ib in plan.escalations: adapt.escalate(root, action.capability, ib.item_id)
       # The actual code re-attempt is a develop skill call; for the runner, only the plan/escalation is deterministic.
   elif isinstance(action, ReEvaluateItem):
       summary = evidence_runner.run(root, action.capability, only_items=[action.item_id])
       actions_log.append(f"ran_evidence: {action.capability} ({summary.compact()})")
   tick_log.write_tick(root, TickLog(tick_id=tick_id, ran_at=now_utc(), actions=actions_log))
   report_path = report.render(root) if actions_log else None
   shippable = isinstance(action, Shippable)
   return TickResult(tick_id=tick_id, action=action, actions_log=actions_log, report_path=report_path, shippable=shippable)
   ```
3. The "LLM-side" of develop and adapt-retry is documented in each skill's SKILL.md — the orchestrator's deterministic core handles validation, planning, evidence runs, escalation file writes, logging, and reporting
4. CLI: `python -m i2e_core.orchestrator` prints the `TickResult` as JSON; exit code per the skill manifest

## Acceptance Criteria

- [x] `tick` returns a `TickResult` whose `actions_log` matches the dispatched action
- [x] No-op tick (Shippable) writes no log file and no report (idempotent)
- [x] Report is invoked exactly once per non-empty tick
- [x] CLI exit code mapping: 0 normal, 1 preflight, 2 unexpected exception

## Implementation Notes

- `TickResult` (Pydantic v2): `tick_id`, `action`, `actions_log`,
  `report_path: Path | None`, `shippable: bool`. `mode="json"` is used
  when serializing for the CLI so `Path` values come out as strings.
- Tick dispatch uses `isinstance` chains on the action union — readable
  and friendly to mypy.
- For `DevelopAndEvidence`: the orchestrator only records
  `ran_develop: <cap> (LLM-driven; subprocess hook deferred)` then calls
  `evidence_runner.run`. Develop itself is LLM-side; the next tick
  converges once develop completes.
- For `AdaptThenRetry`: `adapt.plan` is invoked, an action string is
  logged with the retry/escalation counts, and `adapt.escalate` is
  called for each escalation (best-effort batch — `FileExistsError`
  and other exceptions are swallowed; the planner's
  `has_open_escalation` already filters duplicates).
- The orchestrator never re-triggers develop in-process; the next tick
  picks it up via the decision tree.
- Evidence-runner exceptions are recorded as
  `ran_evidence: <cap> (failed: <msg>)` so the tick still completes.
- `write_tick` is skipped when `actions_log` is empty (spec §9: empty
  ticks are silent). Report is rendered only when `actions_log` is
  non-empty — exactly once per state-changing tick.
- CLI uses argparse with a single `--root` flag, prints `TickResult` as
  JSON to stdout, sends preflight failures to stderr, and maps
  exceptions to exit code 2 via a bare `except Exception` that prints
  a traceback.
