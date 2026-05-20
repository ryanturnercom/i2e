# Task: Provider invocation loop

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-01-skill-manifest, task-02-provider-discovery (epic 02)

## Context

The runner iterates over every evidence item and constraint, resolves the provider for each, invokes it, and aggregates the results. Errors in one provider must not crash the whole run — they're captured as `fail` verdicts with the exception text in `raw.error`.

## Needed from User

None.

## Instructions

1. Implement `src/i2e_core/evidence_runner.py::run`:
   ```
   def run(root, capability, only_items=None) -> RunSummary:
       cap = parse_intent(intents_dir(root)/f"{capability}.md")
       cfg = load_config(root)
       providers = installed_provider_names()
       validate_capability_with_config(cap, cfg, providers)
       prior = read_current(root, capability)
       run_id = new_run_id()
       ctx_base = ProviderContext(root=root, capability=capability, run_id=run_id, cfg=cfg)
       items_to_run = _select(cap, only_items)
       verdicts = {}
       for item in items_to_run:
           try:
               provider = load_provider(item.provider)
               result = provider.invoke(item, ctx_base)
               prev_attempts = (prior.items.get(item.id).attempts_used if prior and item.id in prior.items else 0)
               verdicts[item.id] = to_item_verdict(result, prev_attempts=prev_attempts)
           except Exception as e:
               verdicts[item.id] = ItemVerdict(verdict="fail", attempts_used=prev_attempts+1, raw={"error": str(e)})
       # carry over verdicts for items not selected
       if only_items and prior:
           for id_, v in prior.items.items():
               verdicts.setdefault(id_, v)
       snap = RunSnapshot(run_id=run_id, capability=capability, intent_version=cap.frontmatter.version,
                          collected_at=now_utc(), items=verdicts)
       write_run_snapshot(root, snap)
       write_current(root, CurrentEvidence(capability=capability, last_run=run_id,
                                           intent_version=cap.frontmatter.version, items=verdicts))
       return RunSummary.from_verdicts(verdicts)
   ```
2. `RunSummary(BaseModel)`: `pass_: int`, `fail: int`, `met: int`, `unmet: int`, `trending: int`, `awaiting_human: int`, `total: int`
3. Hide `pass` as a field name by using alias (Pydantic supports it) so the runtime attribute is `pass_` but YAML/JSON keys are `pass`

## Acceptance Criteria

- [x] A capability with one passing pytest case yields `RunSummary(pass_=1, total=1, ...zeros...)`
- [x] A capability where one provider raises an exception still completes the run; the failing item shows `verdict="fail"` with `raw.error` set
- [x] `only_items` re-evaluates the selected items and carries over prior verdicts for the rest
- [x] `attempts_used` increments for non-passing verdicts, resets/preserves correctly on a pass

## Implementation Notes

- Implemented `evidence_runner.run` exactly along the sketch in the task,
  with per-item try/except wrapping both `load_provider` and
  `provider.invoke`. A `FileExistsError` from an async provider gets its
  own catch (see task-04). Any other exception is recorded as
  `ItemVerdict(verdict="fail", attempts_used=prev+1, raw={"error": str(e)})`
  and the loop continues.
- Iteration covers `cap.evidence + cap.constraints` via
  `_capability_items(cap)` so constraints get the same provider
  treatment as evidence items.
- `RunSummary` uses Pydantic alias: `pass_: int = Field(0, alias="pass")`
  with `model_config = ConfigDict(populate_by_name=True, extra="forbid")`.
  Confirmed both `summary.pass_` and `summary.model_dump(by_alias=True)["pass"]`
  work; also `RunSummary.model_validate({"pass": 2, ...})` round-trips.
- Added `RunSummary.compact()` returning the spec'd one-liner
  `"<n> pass, <n> trending, <n> fail"`. The orchestrator can drop it
  into a tick log YAML scalar.
- `_prev_attempts(prior, item_id)` returns 0 when prior is None or the
  item is new; otherwise it returns `prior.items[item_id].attempts_used`.
- `to_item_verdict` already handles the `attempts_used` increment rules
  per provider-result kind (pass/met/awaiting_human do NOT bump; fail /
  unmet / trending DO bump).
- Validation is run up front via
  `validate_capability_with_config(cap, cfg, installed_providers())` and
  re-raised — the runner is a standalone entry point, not just a
  callee from the orchestrator's preflight, so it must guard the same
  rules.
