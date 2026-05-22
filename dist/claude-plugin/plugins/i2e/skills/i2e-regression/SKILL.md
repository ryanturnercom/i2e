---
name: i2e-regression
description: Periodic case + constraint re-validation for shipped (or active, or all) capabilities. Targets stay out of scope — branch 4 owns that path. Demotes shipped → active on any flip to fail / unmet / trending.
license: Apache-2.0
metadata:
  tier: loop
  version: "0.1.0"
  optional: true
---

# i2e-regression

The IDEA loop's branch 4 keeps targets honest via `window:`. There is no
equivalent for cases — once a capability is `shipped`, its pytest cases
never re-run on their own. Code rot, dependency upgrades, or external
regressions can silently break a shipped capability and the dashboard
will not notice.

This skill re-runs every case + constraint for in-scope capabilities and
demotes any shipped capability whose verdicts regress.

## When to use
- On a cadence (Claude `/schedule`, OS scheduler, CI) to catch silent
  regressions in shipped capabilities.
- Ad-hoc after a dependency upgrade or large refactor — pass
  `--status all` to revalidate active and shipped together.
- Scoped to a single capability via `--capability <slug>` when triaging.

## Boundaries
- READ: `.i2e/intents/**`, `.i2e/evidence/**`
- WRITE: `.i2e/evidence/<cap>/**`, `.i2e/logs/regressions/**`,
  and the orchestrator carve-out for `status:` (only on the
  `shipped → active` demote path)
- NEVER WRITE: drafts or retired capabilities; target verdicts in
  current.yaml (targets are preserved verbatim)

## Workflow
1. Default scope is `shipped`. Pass `--status active|all` to widen.
2. For each in-scope capability, invoke
   `i2e_core.evidence_runner.run(root, cap, only_items=[case_and_constraint_ids])`.
   Targets stay out of `only_items` so their verdicts roll forward
   untouched.
3. Any verdict that lands in `{fail, unmet, trending}` on a shipped
   capability flips it back to `active` via the orchestrator's
   carve-out (`_orchestrator_demote_to_active`).
4. A YAML log entry is written to
   `.i2e/logs/regressions/<run_id>.yaml` listing every capability
   touched and the per-item delta.

## Cadence

BYO — call directly, schedule via `/schedule`, or wire to CI. The skill
has no built-in timer.

## CLI

```bash
python -m i2e_core.i2e_regression --status shipped               # default
python -m i2e_core.i2e_regression --status all
python -m i2e_core.i2e_regression --capability shorten-url
```

## Python entry point

```python
from i2e_core.i2e_regression import run

result = run(Path("."), status="shipped")
for delta in result.capabilities:
    if delta.demoted:
        print(f"{delta.capability}: shipped → active (regression)")
```

## Forbidden
- Re-evaluating targets — branch 4's `window:` mechanism owns that.
- Touching draft or retired capabilities — they have no shipped baseline.
- Writing the intent file directly — the demote path goes through the
  orchestrator's narrow status carve-out.
