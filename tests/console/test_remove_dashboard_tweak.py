"""Evidence for the ``remove-dashboard-tweak`` capability.

The Dashboard selector is gone from the Tweaks panel and the
``dashboard`` key no longer exists in the console prefs schema.
"""

from __future__ import annotations

import json
from urllib.parse import quote

from i2e_core.console.prefs import (
    COOKIE_NAME,
    DEFAULT_PREFS,
    parse_prefs_from_cookie,
)
from i2e_core.console.shell import _tweaks_panel


def test_tweaks_panel_has_no_dashboard_axis():
    """The Tweaks panel no longer renders a Dashboard selector."""
    panel = _tweaks_panel(parse_prefs_from_cookie(None))

    # The Dashboard axis — select and all three layout options — is gone.
    assert 'name="dashboard"' not in panel
    assert "<span>Dashboard</span>" not in panel
    assert ">Cockpit<" not in panel
    assert ">IDEA arc<" not in panel
    assert ">Inbox<" not in panel

    # The remaining layout axes are untouched.
    assert 'name="density"' in panel
    assert 'name="sidebar"' in panel
    assert 'name="logs"' in panel


def test_dashboard_pref_key_removed():
    """The ``dashboard`` key is gone from the prefs schema."""
    assert "dashboard" not in DEFAULT_PREFS

    # A stale cookie still carrying a dashboard value is silently dropped,
    # while known keys are still parsed normally.
    encoded = quote(json.dumps({"dashboard": "arc", "density": "dense"}))
    prefs = parse_prefs_from_cookie(f"{COOKIE_NAME}={encoded}")
    assert "dashboard" not in prefs
    assert prefs["density"] == "dense"
