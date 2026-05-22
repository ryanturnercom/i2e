"""Specs view — `/specs` (list) and `/specs/<id>` (detail + reconcile).

Lists every ``.i2e/specs/*.md`` with its derived-intent count. The detail
view shows the rendered spec, the intents whose frontmatter declares this
``spec:``, and a Reconcile button that dispatches the reconcile Job.
"""

from __future__ import annotations

from pathlib import Path

from ...intent import parse_intent
from ...paths import i2e_dir, intents_dir
from .. import ui
from ..shell import page
from ..state import gather


def _specs_dir(root: Path) -> Path:
    return i2e_dir(Path(root)) / "specs"


def _derived_intents_for(root: Path, spec_slug: str) -> list:
    base = intents_dir(Path(root))
    out = []
    if not base.exists():
        return out
    for p in sorted(base.glob("*.md")):
        try:
            cap = parse_intent(p)
        except Exception:
            continue
        if cap.frontmatter.spec == spec_slug:
            out.append(cap)
    return out


def _specs_list_body(root: Path) -> str:
    base = _specs_dir(root)
    rows = []
    if base.exists():
        for p in sorted(base.glob("*.md")):
            slug = p.stem
            count = len(_derived_intents_for(root, slug))
            rows.append(
                f'<li class="spec-row" data-slug="{ui.esc(slug)}">'
                f'<a href="/specs/{ui.esc(slug)}">{ui.mono(slug)}</a>'
                f'<span class="derived-count">{count} derived</span></li>'
            )
    intro = (
        "<div>"
        + ui.eyebrow("Specs")
        + '<h1 class="h1">Source specs</h1>'
        + '<div class="lead">Preserved PRDs/design docs decomposed via '
        '<span class="mono">i2e-spec</span>. Reconcile diffs an edited spec '
        "against the intents it produced.</div></div>"
    )
    if rows:
        body = f'<ul class="specs-list">{"".join(rows)}</ul>'
        inner = f'<section class="card p24">{body}</section>'
    else:
        inner = '<section class="card">' + ui.empty_state(
            "No specs yet", "Run i2e-spec to decompose a PRD or design doc"
        ) + "</section>"
    return f'<div class="stack" id="specs-view">{intro}{inner}</div>'


def render_specs_list(root: Path, *, cookie: str | None = None) -> str:
    root = Path(root)
    return page(
        root=root,
        active="specs",
        state=gather(root),
        eyebrow="Specs",
        title="Source specs",
        path="/specs",
        cookie=cookie,
        body=_specs_list_body(root),
    )


def _spec_detail_body(root: Path, slug: str) -> str:
    spec_path = _specs_dir(root) / f"{slug}.md"
    if not spec_path.exists():
        return (
            f'<div id="spec-detail" data-slug="{ui.esc(slug)}" data-empty="true">'
            + ui.empty_state("Spec not found", slug)
            + "</div>"
        )
    raw = spec_path.read_text(encoding="utf-8")
    derived = _derived_intents_for(root, slug)
    derived_rows = "".join(
        f'<li class="intent-link" data-slug="{ui.esc(c.frontmatter.capability)}" '
        f'data-spec-section="{ui.esc(str(c.frontmatter.spec_section or ""))}">'
        f'<a href="/intent/{ui.esc(c.frontmatter.capability)}">'
        f"{ui.mono(c.frontmatter.capability)}</a>"
        f"{ui.status_badge(c.frontmatter.status)}</li>"
        for c in derived
    )
    derived_block = (
        f'<ul class="derived-list">{derived_rows}</ul>'
        if derived
        else '<p class="mono faded" style="font-size:12px">No derived intents yet.</p>'
    )
    reconcile = (
        f'<form hx-post="/api/specs/{ui.esc(slug)}/reconcile" '
        'hx-target="#toasts" hx-swap="beforeend">'
        '<button type="submit" class="btn">Reconcile with spec</button>'
        "</form>"
    )
    return f"""<div class="stack" id="spec-detail" data-slug="{ui.esc(slug)}">
  <div>
    {ui.eyebrow("Spec")}
    <h1 class="h1">{ui.esc(slug)}</h1>
    <div class="lead">.i2e/specs/{ui.esc(slug)}.md</div>
  </div>
  <section class="card p24">
    <div class="card-head"><h2 class="h2">Derived intents ({len(derived)})</h2>
    {reconcile}</div>
    {derived_block}
  </section>
  <section class="card p0 source-block">
    <div class="sb-bar">{ui.mono(f".i2e/specs/{slug}.md")}
      <span class="push mono faded" style="font-size:11px">read-only</span></div>
    <pre>{ui.esc(raw)}</pre>
  </section>
</div>"""


def render_spec_detail(
    root: Path, slug: str, *, cookie: str | None = None
) -> str:
    root = Path(root)
    return page(
        root=root,
        active="specs",
        state=gather(root),
        eyebrow=slug,
        title="Spec",
        path=f"/specs/{slug}",
        cookie=cookie,
        body=_spec_detail_body(root, slug),
    )
