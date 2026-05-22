"""Capability cards expand on click to surface case + constraint detail.

The report must let a watcher drill from the high-level shippable signal
all the way down to the failing query without leaving the page.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from i2e_core.evidence import CurrentEvidence, ItemVerdict, write_current
from i2e_core.report import build_view_model, render_to_string


def _intent(name: str) -> str:
    return (
        f"---\n"
        f"capability: {name}\n"
        f"created: '2026-05-20'\n"
        f"updated: '2026-05-20'\n"
        f"version: 1\n"
        f"status: active\n"
        f"watcher: '@me'\n"
        f"---\n"
        f"\n"
        f"# {name}\n"
        f"\n"
        f"## Evidence of success\n"
        f"\n"
        f"- id: {name}-case\n"
        f"  type: case\n"
        f"  provider: pytest\n"
        f"  query: tests/test_{name.replace('-', '_')}.py::test_thing\n"
        f"  expect: passes\n"
        f"  effort: medium\n"
        f"\n"
        f"## Constraints\n"
        f"\n"
        f"- id: {name}-c1\n"
        f"  provider: pytest\n"
        f"  query: tests/{name.replace('-', '_')}_constraint.py::test_invariant\n"
        f"  expect: passes\n"
        f"  effort: low\n"
    )


def _seed(root: Path, slug: str) -> None:
    for sub in ("intents", "evidence", "pending", "logs", "context"):
        (root / ".i2e" / sub).mkdir(parents=True, exist_ok=True)
    (root / ".i2e" / "intents" / f"{slug}.md").write_text(
        _intent(slug), encoding="utf-8"
    )
    cur = CurrentEvidence(
        capability=slug,
        last_run="2026-05-20-aaa000",
        intent_version=1,
        items={
            f"{slug}-case": ItemVerdict(
                verdict="fail",
                value="boom",
                attempts_used=1,
                last_observed=datetime.now(timezone.utc),
                raw={"output": "AssertionError: boom"},
            ),
            f"{slug}-c1": ItemVerdict(
                verdict="pass",
                attempts_used=0,
                last_observed=datetime.now(timezone.utc),
            ),
        },
    )
    write_current(root, cur)


def test_implemented(tmp_path: Path) -> None:
    _seed(tmp_path, "alpha")

    # --- view model carries query/expect down to each item -----------------
    vm = build_view_model(tmp_path)
    assert len(vm.capabilities) == 1
    cap_view = vm.capabilities[0]
    by_id = {it.id: it for it in cap_view.items}
    case = by_id["alpha-case"]
    assert case.query == "tests/test_alpha.py::test_thing"
    assert case.expect == "passes"
    constraint = by_id["alpha-c1"]
    assert constraint.type == "constraint"
    assert constraint.query == "tests/alpha_constraint.py::test_invariant"
    assert constraint.expect == "passes"

    # --- HTML wraps the item grid in a <details> so the card expands on click
    html = render_to_string(tmp_path)
    assert '<details class="case-details">' in html
    # The summary text must indicate cases + constraints so the user knows
    # what's behind the disclosure.
    assert "Cases &amp; constraints" in html

    # The cap card's <details> must come AFTER the cap header & status
    # controls, otherwise clicking the title would jump to the wrong section.
    cap_section = html.split('id="cap/alpha"', 1)[1].split("</section>", 1)[0]
    assert cap_section.index('class="status-controls"') < cap_section.index(
        '<details class="case-details">'
    )

    # Drill-down detail is visible inside the card.
    assert "alpha-case" in cap_section
    assert "tests/test_alpha.py::test_thing" in cap_section
    assert "passes" in cap_section
    # The failed last value shows up so the watcher can read the error
    # without leaving the page.
    assert "boom" in cap_section

    # Constraints also rendered inside the details disclosure.
    assert "alpha-c1" in cap_section
    assert "tests/alpha_constraint.py::test_invariant" in cap_section

    # Deep-link IDs preserved through the structural change.
    assert 'id="item/alpha/alpha-case"' in html
    assert 'id="item/alpha/alpha-c1"' in html

    # Details starts collapsed by default — the "open" attribute is absent.
    # (The browser opens it on user click; this asserts default state.)
    details_open_tag = '<details class="case-details" open'
    assert details_open_tag not in html
