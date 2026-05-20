# Task: i2e-provider-survey

**Status:** [✓] Completed
**Started:** 2026-05-19
**Completed:** 2026-05-19

**Dependencies:** task-04-provider-human (epic 02)

## Context

Survey provider reuses the async pending pattern from `i2e-provider-human`. Differences:

- `verdict_options` are typically numeric (NPS 0–10) or scale (1–5)
- The `ask:` is structured: includes the question, the rating scale, and a free-text follow-up

## Needed from User

None (asynchronous; humans answer the survey).

## Instructions

1. Create `.claude/skills/i2e-provider-survey/SKILL.md`
2. Create `provider.py` that reuses `i2e_core.pending` and writes a pending file with:
   - `kind: "human_evaluation"`
   - `verdict_options: ["1","2","3","4","5","6","7","8","9","10"]` (configurable via `item.query` JSON: `{"scale":"nps"}` or `{"scale":"likert"}`)
   - `ask` formatted from `item.query`'s `prompt` field
3. The resolver (`pending.resolve_to_verdict`) needs an extension: for surveys, map the chosen rating to a Target shape:
   - `value: "<rating>"`, `met` based on `expect: >=N` (e.g. `>=8` for NPS promoters)
4. Update `resolve_to_verdict` to inspect `pf.kind` AND the original item type — keep that conversion logic centralized

## Acceptance Criteria

- [x] Skill discovered as `survey`
- [x] First call writes a pending file with numeric `verdict_options`
- [x] On resolution `"9"` with `expect: ">=8"`, the resolved verdict is `met` with `value="9"`
- [x] Resolution `"5"` with `expect: ">=8"` resolves to `unmet`

## Implementation Notes

- Created `.claude/skills/i2e-provider-survey/{SKILL.md,provider.py}`.
- Reuses `i2e_core.pending.write_pending` with `kind="human_evaluation"`
  (no new pending kind needed — `verdict_options` carries the numeric scale).
- Supports two scales out-of-the-box: `nps` (0-10, default) and `likert`
  (1-5). Unknown scales raise `ValueError`.
- `item.query` is a JSON object: `{"prompt": "...", "scale": "nps",
  "followup": "..."}`. Invalid JSON or missing `prompt` raises `ValueError`.
- Extended `pending.resolve_to_verdict` with a numeric branch: if
  `resolution` parses as a number AND `expect` is a comparison expression
  (parsed via `expect_parser.parse_expect`), emits a Target-shape
  `ItemVerdict(verdict="met"|"unmet", value=<rating>)`. Falls through to the
  legacy yes/no/partial branch otherwise — full backward compat.
- Tests: `tests/providers/test_survey_provider.py` (13 tests, including
  back-compat for the existing human yes/no/partial flow).
