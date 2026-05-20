# Task: State-to-view-model mapper

**Status:** [ ] Pending

**Dependencies:** task-02-html-template

## Context

`render(root)` builds a `ReportViewModel` from disk and pipes it through Jinja2. The view model is fully serializable and unit-testable.

## Needed from User

None.

## Instructions

1. Create `src/i2e_core/report/view_model.py`:
   - `CapabilityView(BaseModel)`: `slug`, `version`, `status`, `watcher`, `items: list[ItemView]`, `summary: dict[str,int]`
   - `ItemView(BaseModel)`: `id`, `type`, `provider`, `verdict`, `value`, `attempts_used`, `max_attempts`, `last_observed`, `pending_basename`
   - `PendingView(BaseModel)`: `filename`, `kind`, `capability`, `item_id`, `ask`, `verdict_options`, `attempts`, `status`
   - `TickView(BaseModel)`: `tick_id`, `ran_at`, `actions`
   - `ReportViewModel(BaseModel)`: `project_name: str`, `generated_at: datetime`, `shippable: bool`, `capabilities: list[CapabilityView]`, `pending: list[PendingView]`, `ticks: list[TickView]`, `serve_url: str | None`
2. Implement `build_view_model(root: Path) -> ReportViewModel`:
   - List active capabilities; for each, load intent + current.yaml; compute max_attempts per item using config
   - List open pendings
   - List last 10 tick logs
   - Read `.i2e/.serve.url` if present
   - `shippable = all(v in {"pass","met"} for cap in capabilities for v in cap.items.verdict)`
3. Implement `render(root) -> Path`:
   - `vm = build_view_model(root)`; render `report.html.j2` with it; atomic-write to `.i2e/report.html`; return that path

## Acceptance Criteria

- [ ] `build_view_model` returns a populated model for a project with one capability + one open pending + 2 ticks
- [ ] `shippable` is True only when every item's verdict is `pass` or `met`
- [ ] `render` writes a non-empty HTML file to `.i2e/report.html`
- [ ] Re-running `render` produces byte-identical output when state is unchanged (deterministic — use stable serialization)
