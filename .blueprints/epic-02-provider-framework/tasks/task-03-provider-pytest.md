# Task: i2e-provider-pytest skill + runner

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-01-provider-contract, task-02-provider-discovery

## Context

`i2e-provider-pytest` is the reference Case/Constraint provider. It runs `pytest <query>` and translates the exit code into a verdict.

A query looks like `tests/test_shorten.py::test_returns_7_char_code` (file or nodeid). It must be invoked with a working directory of the project root and must not pollute that directory (use `--no-header --no-summary -q`).

## Needed from User

None.

## Instructions

1. Create the skill folder at `.claude/skills/i2e-provider-pytest/` with two files:

**`SKILL.md`**
```markdown
---
name: i2e-provider-pytest
description: Run pytest against a query (file::nodeid). Returns a pass/fail Case verdict. Use for cases or constraints whose provider is "pytest".
license: Apache-2.0
metadata:
  tier: provider
  version: "0.1.0"
---

# i2e-provider-pytest

Collects evidence by running pytest. See `provider.py` for the Python entry point; `i2e-evidence` invokes that directly. This SKILL.md is the registration marker for provider discovery.

## Inputs
- `query` — pytest node id (file path, file::test, or `-k expr`)
- `expect` — must be the literal string `passes`

## Returns
- `{ verdict: "pass" | "fail", output: "<last 40 lines of pytest output>" }`
```

**`provider.py`**
```python
from __future__ import annotations
import subprocess
from datetime import datetime, timezone
from i2e_core.provider import CaseResult, ProviderContext
from i2e_core.intent import EvidenceItem, Constraint

class PytestProvider:
    name = "pytest"

    def invoke(self, item, ctx: ProviderContext) -> CaseResult:
        result = subprocess.run(
            ["pytest", item.query, "--no-header", "-q", "--tb=short"],
            cwd=ctx.root, capture_output=True, text=True, timeout=600,
        )
        output_tail = "\n".join((result.stdout + result.stderr).splitlines()[-40:])
        return CaseResult(
            verdict="pass" if result.returncode == 0 else "fail",
            output=output_tail,
        )

provider = PytestProvider()
```

2. Update `installed_provider_names()` (epic 02 task-02) and `load_provider()` to pick it up — should already work if discovery scans `.claude/skills/`
3. Add a smoke test in `tests/providers/test_pytest_provider.py`:
   - Create a tiny `tests/_fixtures/passing_test.py` and `failing_test.py`
   - Assert `PytestProvider().invoke(...)` returns `pass` and `fail` respectively
   - Use a real subprocess (don't mock — the spec is "forced evidence", let's eat our own dog food)

## Acceptance Criteria

- [x] `.claude/skills/i2e-provider-pytest/SKILL.md` exists and parses as YAML frontmatter
- [x] `load_provider("pytest")` returns a `Provider` whose `name == "pytest"`
- [x] Smoke test demonstrates a passing query returns `verdict="pass"`
- [x] Smoke test demonstrates a failing query returns `verdict="fail"` and `output` contains the failure traceback
- [x] Timeout is enforced — a query that hangs forever fails after 600s with a clear `fail` verdict (not a stack trace)

## Implementation Notes

- Subprocess invoked with `[sys.executable, "-m", "pytest", ...]` so Windows tests don't depend on `pytest` being on PATH inside the subprocess shell.
- `subprocess.TimeoutExpired` is caught and translated into a `CaseResult(verdict="fail", ...)` — providers never raise, they always return a verdict.
- Output is truncated to the last 40 lines via splitlines + slice, joining stdout and stderr to give the failure traceback context.
- Fixture pytest files live in `tests/providers/_fixtures/` and are masked from collection via a local `conftest.py` `collect_ignore_glob`.
