# Task: Provider discovery from installed skills

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-01-provider-contract

## Context

Spec §5 rule 2: *every provider named in an evidence item must have a matching installed `i2e-provider-*` skill*. To enforce that, the validator needs a function that returns the set of installed provider names.

Skills are installed under `~/.claude/skills/` (user-level) and `./.claude/skills/` (project-level). A provider named `pytest` lives at `i2e-provider-pytest/`.

Each provider skill folder is expected to ship:
- `SKILL.md` (the agentskills.io manifest)
- `provider.py` — a module exposing `provider: Provider` (instance) that conforms to the contract

## Needed from User

None.

## Instructions

1. Create `src/i2e_core/provider/discovery.py`:
   - `def installed_provider_names(extra_paths: list[Path] | None = None) -> set[str]`:
     - Scans `~/.claude/skills/` and `<project_root>/.claude/skills/`
     - Returns names by stripping the `i2e-provider-` prefix from each matching folder
     - `extra_paths` lets tests inject a fake skills dir
   - `def load_provider(name: str) -> Provider`:
     - Finds the folder, dynamically imports `<folder>/provider.py` via `importlib.util.spec_from_file_location`
     - Returns the module's `provider` attribute
     - Caches loaded providers (`functools.lru_cache`-style — keyed by name + mtime)
2. Both functions resolve `~` and follow symlinks
3. If the same provider name appears in user-level and project-level dirs, project-level wins (closer = override)
4. Add a CLI helper `python -m i2e_core.provider.discovery` that prints installed providers — useful for debugging

## Acceptance Criteria

- [x] `installed_provider_names()` returns `set()` when no skills dir exists (no exception)
- [x] With a fake skills dir containing `i2e-provider-pytest/` and `i2e-provider-human/`, returns `{"pytest","human"}`
- [x] Project-local skill overrides a user-level skill with the same name (test with two `extra_paths` and assert the project one is loaded)
- [x] `load_provider("missing")` raises `LookupError` with a hint pointing to the skills dirs that were scanned
- [x] CLI helper prints one name per line

## Implementation Notes

- Scan order: `~/.claude/skills/` → `<cwd>/.claude/skills/` → `extra_paths` (in given order). Later wins, so passing `[user, proj]` makes project-local override user-level.
- Caching is keyed by `(provider.py absolute path, mtime)` so editing the provider invalidates the cache without an explicit clear. Tests use `clear_cache()` to reset between cases.
- `load_provider` raises distinct errors per failure mode: `LookupError` if folder absent or `provider.py` missing; `AttributeError` if the module loaded but didn't expose `provider`.
- CLI entrypoint is at `python -m i2e_core.provider.discovery` (printed one provider name per line, sorted).
