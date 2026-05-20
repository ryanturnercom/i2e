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
