# Task: Intent file parser + Pydantic models

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-01-project-skeleton

## Context

Capability intent files are Markdown with YAML frontmatter (spec §2.1). The body has free-form prose, an `## Evidence of success` section containing a YAML list, and a `## Constraints` section containing a YAML list. Every list item shares the same shape.

The parser must round-trip cleanly (parse → model → re-serialize produces semantically identical content) so the `i2e-intent` skill can edit files without churning whitespace.

## Needed from User

None.

## Instructions

1. Create `src/i2e_core/intent.py` with Pydantic v2 models:
   - `EvidenceItem(BaseModel)`:
     - `id: str` (required, kebab-case validator)
     - `type: Literal["case","target"]` (required for evidence; constraints set this elsewhere)
     - `provider: str` (required)
     - `query: str` (required; multi-line OK)
     - `expect: str` (required)
     - `window: str | None = None` (e.g. `5m`, `7d` — only meaningful for targets)
     - `effort: str = "medium"` (validated against tier set in config loader at validate-time, not at parse-time)
   - `Constraint(BaseModel)`: same shape minus `type` and `window`; type fixed to `"constraint"` at runtime
   - `Frontmatter(BaseModel)`: `capability: str`, `created: date`, `updated: date`, `version: int`, `status: Literal["draft","active","retired"]`, `watcher: str = "@me"`
   - `Capability(BaseModel)`: `frontmatter: Frontmatter`, `description: str` (the prose body before `## Evidence of success`), `evidence: list[EvidenceItem]`, `constraints: list[Constraint]`
2. Parser:
   - `parse_intent(path: Path) -> Capability` — use `python-frontmatter` for the YAML header; split the body by `## Evidence of success` and `## Constraints` headings; YAML-parse each section's list
   - `serialize_intent(cap: Capability) -> str` — emit canonical Markdown (stable key order, two-space indented YAML lists)
   - `write_intent(cap: Capability, path: Path)` — calls serialize + atomic write (use `io_utils.atomic_write` from task-06)
3. The body splitter must tolerate:
   - Description containing `##` subheadings (only split on the two named section headings)
   - Constraints section being absent (treat as empty)
   - List items written as YAML block (the spec's example style) — leading `- ` followed by indented key/value pairs

## Acceptance Criteria

- [✓] Parsing the spec's `shorten-url.md` example (recreate it in `tests/fixtures/`) succeeds and yields 3 evidence items + 2 constraints
- [✓] `serialize_intent(parse_intent(p))` produces output that re-parses to an equal `Capability`
- [✓] Missing `## Constraints` section yields `constraints == []`
- [✓] Items missing `id`, `provider`, `query`, or `expect` raise `ValidationError` on parse
- [✓] Kebab-case validator rejects `myItem` or `my_item` for `id`

## Implementation Notes

- `src/i2e_core/intent.py` exposes `EvidenceItem`, `Constraint`, `Frontmatter`, `Capability`, plus `parse_intent`, `serialize_intent`, `write_intent`.
- Frontmatter is parsed with `python-frontmatter`; the body is split at the literal headings `## Evidence of success` and `## Constraints` only — subheadings inside the description are preserved.
- YAML 1.1 booleans (`yes`/`no`/`on`/`off`) and numeric-looking scalars are coerced back to `str` for the known string fields (`expect`, `query`, etc.) so `expect: yes` and `expect: 0` round-trip safely.
- Serialization emits a stable key order (`id, type, provider, query, expect, window, effort` for evidence; `id, provider, query, expect, effort` for constraints) and uses block-style `|` literals for multi-line `query` values.
- `write_intent` uses `io_utils.atomic_write` for crash-safety.
