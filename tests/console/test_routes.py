"""Dashboard view renders the cockpit layout from a minimal .i2e/ tree."""

from __future__ import annotations

from pathlib import Path

from i2e_core.console.views.dashboard import render_dashboard


def _bootstrap(root: Path) -> None:
    (root / ".i2e" / "intents").mkdir(parents=True)
    (root / ".i2e" / "evidence").mkdir(parents=True)
    (root / ".i2e" / "logs").mkdir(parents=True)
    (root / ".i2e" / "pending").mkdir(parents=True)


def test_dashboard_renders(tmp_path):
    _bootstrap(tmp_path)
    html = render_dashboard(tmp_path)
    # Cockpit layout expectations: at minimum the dashboard chrome and
    # the four strips must be present so htmx targeting works against
    # stable IDs even when the data is empty.
    assert "<html" in html.lower()
    assert 'id="needs-you"' in html
    assert 'id="shippability"' in html
    assert 'id="workers"' in html
    assert 'id="capabilities"' in html
    assert 'id="recent-ticks"' in html
