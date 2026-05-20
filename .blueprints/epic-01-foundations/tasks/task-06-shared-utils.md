# Task: Shared utils (paths, run-id, atomic writes)

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-01-project-skeleton

## Context

Every other module needs the same primitives:
- Canonical path resolver (where does `.i2e/` live? where do intents go?)
- Run-id generator (`YYYY-MM-DD-<6 hex>`)
- Atomic file write (write-then-rename so a crash never leaves a partial file)
- YAML dump helper with stable key order

Pulling these into one module keeps the rest of the package thin and consistent.

## Needed from User

None.

## Instructions

1. Create `src/i2e_core/paths.py`:
   - `def find_root(start: Path | None = None) -> Path` — walks up from `start` (default `Path.cwd()`) until it finds a `.i2e/` directory; raises `RuntimeError` if none found
   - Path helpers: `intents_dir(root)`, `evidence_dir(root, cap)`, `runs_dir(root, cap)`, `current_path(root, cap)`, `pending_dir(root)`, `logs_dir(root)`, `context_dir(root)`, `config_path(root)`, `report_path(root)`, `serve_url_path(root)`
2. Create `src/i2e_core/runid.py`:
   - `def new_run_id(now: datetime | None = None) -> str` — returns `YYYY-MM-DD-<6 hex>`. Hex is `secrets.token_hex(3)`.
   - `def parse_run_id(s: str) -> tuple[date, str]`
3. Create `src/i2e_core/io_utils.py`:
   - `def atomic_write(path: Path, data: str | bytes) -> None` — writes to `path.with_suffix(path.suffix + ".tmp")` then `os.replace`
   - `def dump_yaml(obj: Any) -> str` — `yaml.safe_dump(obj, sort_keys=False, default_flow_style=False, allow_unicode=True)`
   - `def load_yaml(path: Path) -> Any` — `yaml.safe_load(path.read_text(encoding="utf-8"))`
4. All path helpers return `pathlib.Path`. None of them create directories — callers do that explicitly.

## Acceptance Criteria

- [✓] `find_root()` returns the project root when called from any subdirectory
- [✓] `find_root()` raises `RuntimeError` if `.i2e/` is missing (with a hint to run `i2e-intent` first)
- [✓] `new_run_id()` produces strings matching `^\d{4}-\d{2}-\d{2}-[0-9a-f]{6}$`
- [✓] Two consecutive `new_run_id()` calls return different ids
- [✓] `atomic_write` survives a simulated crash mid-write (the target file remains untouched if the `.tmp` write fails)
- [✓] `dump_yaml({"b":1, "a":2})` preserves key order (returns `"b: 1\na: 2\n"`)

## Implementation Notes

- `src/i2e_core/paths.py` provides `find_root` (walks upward, hint mentions `i2e-intent`) plus every canonical helper (`intents_dir`, `evidence_dir`, `runs_dir`, `current_path`, `pending_dir`, `logs_dir`, `context_dir`, `config_path`, `report_path`, `serve_url_path`, plus internal `i2e_dir`/`evidence_root`).
- `src/i2e_core/runid.py` uses `secrets.token_hex(3)` and supports both generation and parsing.
- `src/i2e_core/io_utils.py` writes via `os.replace` after a sibling `.tmp` file — atomic on Windows. `dump_yaml`/`load_yaml` use `yaml.safe_*` with `sort_keys=False` and `allow_unicode=True`.
