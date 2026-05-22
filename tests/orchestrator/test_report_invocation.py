"""Regression tests for the orchestrator → report.render auto-invocation."""

from __future__ import annotations

from pathlib import Path

from i2e_core.orchestrator import tick
from i2e_core.paths import logs_dir, report_path

from .conftest import FakeProvider, always_pass


def _basic_evidence() -> list[dict]:
    return [
        {
            "id": "case-a",
            "type": "case",
            "provider": "pytest",
            "query": "tests/test_a.py",
            "expect": "passes",
            "effort": "medium",
        }
    ]


def test_tick_renders_real_report_with_deep_link_id(
    project: Path, write_intent, patch_providers
):
    """A non-empty tick must produce ``.i2e/report.html`` containing the cap's deep-link id.

    A single-case all-green capability auto-promotes to ``shipped`` on the
    first tick (spec §6.1), so the anchor lives in the Shipped section.
    """
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent("alpha", evidence=_basic_evidence(), version=1)

    result = tick(project)

    rp = report_path(project)
    assert rp.exists()
    text = rp.read_text(encoding="utf-8")
    assert 'id="shipped/alpha"' in text
    assert result.report_path == rp
    assert result.report_link is not None
    assert "#shipped/alpha" in result.report_link


def test_report_mtime_at_least_tick_log_mtime(
    project: Path, write_intent, patch_providers
):
    """Spec: the report is refreshed after the tick log lands."""
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent("alpha", evidence=_basic_evidence(), version=1)
    tick(project)
    tick_logs = list(logs_dir(project).glob("*-tick.yaml"))
    assert len(tick_logs) == 1
    rp = report_path(project)
    assert rp.stat().st_mtime >= tick_logs[0].stat().st_mtime


def test_shippable_tick_does_not_touch_report(
    project: Path, write_intent, write_current_for, patch_providers
):
    """A steady-state shipped project produces ``Shippable`` and writes no report.

    Active + all-green capabilities would auto-promote on the next tick
    (§6.1, intent-shipped-status); to exercise the no-op steady state
    we set the capability up as shipped from the start.
    """
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent("alpha", evidence=_basic_evidence(), version=1, status="shipped")
    write_current_for(
        "alpha",
        {"case-a": {"verdict": "pass", "attempts_used": 0}},
        intent_version=1,
    )
    rp = report_path(project)
    assert not rp.exists()  # precondition
    result = tick(project)
    assert result.shippable is True
    assert result.report_path is None
    # The orchestrator must NOT have created the file for an empty tick.
    assert not rp.exists()


def test_report_link_uses_serve_url_when_available(
    project: Path, write_intent, patch_providers
):
    """If ``.serve.url`` exists, ``TickResult.report_link`` uses HTTP."""
    (project / ".i2e" / ".serve.url").write_text(
        "http://127.0.0.1:54321/", encoding="utf-8"
    )
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent("alpha", evidence=_basic_evidence(), version=1)
    result = tick(project)
    assert result.report_link is not None
    assert result.report_link.startswith("http://127.0.0.1:54321/")
    # alpha auto-promoted to shipped on the first all-green tick (§6.1).
    assert "#shipped/alpha" in result.report_link
