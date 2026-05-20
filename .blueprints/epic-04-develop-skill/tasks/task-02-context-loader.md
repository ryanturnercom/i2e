# Task: Context loader for .i2e/context/

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-06-shared-utils (epic 01)

## Context

`.i2e/context/` holds standing reference docs (ARCHITECTURE.md, DESIGN.md, glossary, conventions) — spec §3. They're read by `i2e-develop` but never proven; they ground the AI's choices without being evidence themselves.

## Needed from User

None.

## Instructions

1. Add `src/i2e_core/context.py`:
   - `def list_context_files(root: Path) -> list[Path]` — returns all `*.md` files under `.i2e/context/` (recursive), sorted by path
   - `def load_context(root: Path, max_chars: int = 80_000) -> dict[str, str]` — returns `{relative_path: content}` truncated to `max_chars` total across all files (FIFO truncation, document boundaries preserved). Logs a warning when truncating.
   - `def context_summary(root: Path) -> str` — a one-line-per-file index used by develop to decide what to pull
2. Provide a default seed `tests/fixtures/context_seed/ARCHITECTURE.md` for tests
3. Document in the SKILL.md (task-01) that develop's first action is `list_context_files` so the LLM knows what reference material exists before loading any of it

## Acceptance Criteria

- [✓] `list_context_files` returns empty list when `.i2e/context/` is empty (no error)
- [✓] `load_context` respects `max_chars` and never returns more than that total length
- [✓] `context_summary` produces one line per file with the file's first heading or first line
- [✓] Files are sorted deterministically (so retries see the same order)

## Implementation Notes

- `list_context_files` returns absolute `Path` objects sorted by path string;
  empty list when the directory is missing (does not raise).
- `load_context` truncates at document boundaries: if adding the next file
  would exceed `max_chars`, the file is *omitted entirely* (never partially
  appended). This keeps every returned value a complete document, which is
  what the LLM expects. A warning is emitted via the `i2e_core.context`
  logger when any file is truncated.
- `context_summary` produces `"<relative_path>: <first heading or first line>"`
  per file, joined with `\n` (no trailing newline). Empty files render as
  `"<relative_path>:"` (no value after the colon).
- Seeded `tests/fixtures/context_seed/ARCHITECTURE.md` and `DESIGN.md` for
  the new `tests/develop/conftest.py::develop_project_with_context` fixture.
