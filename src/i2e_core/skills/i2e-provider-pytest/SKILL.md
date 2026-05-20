---
name: i2e-provider-pytest
description: Run pytest against a query (file::nodeid). Returns a pass/fail Case verdict. Use for cases or constraints whose provider is "pytest".
license: Apache-2.0
metadata:
  tier: provider
  version: "0.1.0"
  bundled: true
---

# i2e-provider-pytest (bundled)

Reference Case/Constraint provider — ships with `i2e_core` so every install has it without a separate skill registration. User-level (`~/.claude/skills/`) and project-local (`<cwd>/.claude/skills/`) copies still override this one.

## Inputs
- `query` — pytest node id (file path, `file::test`, or `-k expr`)
- `expect` — must be the literal string `passes`

## Returns
- `{ verdict: "pass" | "fail", output: "<last 40 lines of pytest output>" }`
