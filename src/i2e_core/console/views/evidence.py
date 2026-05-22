"""Evidence view — cross-capability lens.

Tabs:

- Catalogue (default): every case / target / constraint across every
  capability. Filters: type / verdict / provider / watcher.
- Runs: chronological feed of every evidence run, newest first.
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Literal

from ...evidence import read_current
from ...intent import parse_intent
from ...paths import i2e_dir, intents_dir

EvidenceTab = Literal["catalogue", "runs"]


def _evidence_root(root: Path) -> Path:
    return i2e_dir(Path(root)) / "evidence"


def render_evidence_catalogue(root: Path) -> str:
    root = Path(root)
    base = intents_dir(root)
    rows: list[str] = []
    if base.exists():
        for p in sorted(base.glob("*.md")):
            try:
                cap = parse_intent(p)
            except Exception:
                continue
            cur = read_current(root, cap.frontmatter.capability)
            verdict_map = cur.items if cur else {}
            watcher = cap.frontmatter.watcher
            for item in list(cap.evidence) + [
                # Constraints rendered with type='constraint' for the catalogue.
                type("ItemView", (), {
                    "id": c.id, "type": "constraint", "provider": c.provider
                })()
                for c in cap.constraints
            ]:
                v = verdict_map.get(item.id)
                verdict = v.verdict if v else "—"
                rows.append(
                    f'<tr class="ev-row"'
                    f' data-capability="{escape(cap.frontmatter.capability)}"'
                    f' data-type="{escape(item.type)}"'
                    f' data-item-id="{escape(item.id)}"'
                    f' data-provider="{escape(item.provider)}"'
                    f' data-verdict="{escape(verdict)}"'
                    f' data-watcher="{escape(watcher)}">'
                    f"<td>{escape(cap.frontmatter.capability)}</td>"
                    f"<td>{escape(item.type)}</td>"
                    f"<td>{escape(item.id)}</td>"
                    f"<td>{escape(item.provider)}</td>"
                    f"<td>{escape(verdict)}</td>"
                    f"<td>{escape(watcher)}</td>"
                    f"</tr>"
                )
    table = (
        f'<table class="catalogue">'
        f"<thead><tr><th>capability</th><th>type</th><th>id</th><th>provider</th><th>verdict</th><th>watcher</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>i2e Console — Evidence</title></head>
<body>
<main id="evidence-view" data-tab="catalogue">
  <nav class="tabs">
    <a class="tab active" data-tab="catalogue">Catalogue</a>
    <a class="tab" data-tab="runs" href="/evidence?tab=runs">Runs</a>
  </nav>
  {table}
</main>
</body>
</html>
"""


def render_evidence_runs(root: Path) -> str:
    """Chronological feed of every evidence run, newest first."""
    root = Path(root)
    base = _evidence_root(root)
    rows: list[tuple[float, str]] = []
    if base.exists():
        for cap_dir in sorted(p for p in base.iterdir() if p.is_dir()):
            runs_dir = cap_dir / "runs"
            if not runs_dir.exists():
                continue
            for run_file in runs_dir.glob("*.yaml"):
                mtime = run_file.stat().st_mtime
                rows.append(
                    (
                        mtime,
                        f'<li class="run-row"'
                        f' data-capability="{escape(cap_dir.name)}"'
                        f' data-run="{escape(run_file.stem)}">'
                        f'<a href=".i2e/evidence/{escape(cap_dir.name)}/runs/{escape(run_file.name)}">'
                        f"{escape(cap_dir.name)} / {escape(run_file.stem)}"
                        f"</a></li>",
                    )
                )
    rows.sort(key=lambda t: t[0], reverse=True)
    body = (
        f'<ol class="runs-feed">{"".join(html for _, html in rows)}</ol>'
        if rows
        else '<p class="empty">No evidence runs yet</p>'
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>i2e Console — Evidence Runs</title></head>
<body>
<main id="evidence-view" data-tab="runs">
  <nav class="tabs">
    <a class="tab" data-tab="catalogue" href="/evidence">Catalogue</a>
    <a class="tab active" data-tab="runs">Runs</a>
  </nav>
  {body}
</main>
</body>
</html>
"""
