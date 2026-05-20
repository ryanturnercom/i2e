"""Reporting subsystem — renders ``.i2e/report.html`` from current state.

``render(root)`` is the deterministic public entry point. The orchestrator
calls it after any state-changing tick. Same input state → same byte-
identical HTML output (the renderer pulls a deterministic ``generated_at``
from the latest tick log's ``ran_at`` rather than wall-clock time).

Use :func:`render_to_string` from tests that want HTML without touching disk.
Deep-link helpers live in :mod:`i2e_core.report.links`.
"""

from __future__ import annotations

from .view_model import (
    CapabilityView,
    ItemView,
    PendingView,
    ReportViewModel,
    TickView,
    build_view_model,
    render,
    render_main_to_string,
    render_to_string,
)

__all__ = [
    "CapabilityView",
    "ItemView",
    "PendingView",
    "ReportViewModel",
    "TickView",
    "build_view_model",
    "render",
    "render_main_to_string",
    "render_to_string",
]
