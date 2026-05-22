#!/usr/bin/env bash
# i2e-serve — start the localhost report server in the foreground.
# Blocks until Ctrl+C; the server dies when this terminal closes.
#
# Installed into .i2e/ by `python -m i2e_core.init`. Edit freely;
# re-run init with --force-scripts to restore the shipped version.
set -euo pipefail

# Project root is the parent of the .i2e/ directory holding this script.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"

# Resolve a Python interpreter that can import i2e_core.
# Set I2E_PYTHON to override the search.
i2e_python() {
  local cand
  for cand in "${I2E_PYTHON:-}" \
              "$ROOT/.venv/Scripts/python.exe" \
              "$ROOT/.venv/bin/python" \
              python3 python; do
    if [[ -n "$cand" ]] && command -v "$cand" >/dev/null 2>&1; then
      printf '%s\n' "$cand"
      return 0
    fi
  done
  return 1
}

PYTHON="$(i2e_python)" || {
  echo "i2e: no Python interpreter found (set I2E_PYTHON, or create a .venv)" >&2
  exit 1
}

exec "$PYTHON" -m i2e_core.serve start --root "$ROOT"
