"""Tests for :func:`i2e_core.orchestrator.preflight`."""

from __future__ import annotations

from pathlib import Path

from i2e_core.orchestrator import preflight

from .conftest import FakeProvider, always_pass


def _valid_evidence() -> list[dict]:
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


def test_preflight_passes_with_valid_active_intent(
    project: Path, write_intent, patch_providers
):
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent("alpha", evidence=_valid_evidence())
    res = preflight(project)
    assert res.valid is True
    assert res.errors == {}


def test_preflight_fails_on_unknown_provider(
    project: Path, write_intent, patch_providers
):
    """An active intent referencing an uninstalled provider must fail preflight."""
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    # `datadog` is not installed in the fake registry.
    write_intent(
        "alpha",
        evidence=[
            {
                "id": "target-x",
                "type": "target",
                "provider": "datadog",
                "query": "redirect_latency",
                "expect": "<50ms",
                "effort": "medium",
            }
        ],
    )
    res = preflight(project)
    assert res.valid is False
    assert "alpha" in res.errors
    joined = " | ".join(res.errors["alpha"])
    assert "datadog" in joined


def test_preflight_fails_when_intent_has_no_items(
    project: Path, write_intent, patch_providers
):
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent("empty-cap", evidence=[], constraints=[])
    res = preflight(project)
    assert res.valid is False
    assert "empty-cap" in res.errors
    assert any("no evidence or constraints" in e for e in res.errors["empty-cap"])


def test_preflight_ignores_draft_and_retired_intents(
    project: Path, write_intent, patch_providers
):
    """Draft/retired intents with otherwise-invalid contents must NOT block preflight."""
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    # Draft with an unknown provider — should be ignored.
    write_intent(
        "draft-cap",
        status="draft",
        evidence=[
            {
                "id": "x",
                "type": "case",
                "provider": "ghost",
                "query": "q",
                "expect": "passes",
                "effort": "medium",
            }
        ],
    )
    # Retired and empty — should also be ignored.
    write_intent("retired-cap", status="retired", evidence=[], constraints=[])
    # One genuinely valid active intent so the result is "valid".
    write_intent("alpha", evidence=_valid_evidence())
    res = preflight(project)
    assert res.valid is True
    assert res.errors == {}


def test_preflight_aggregates_errors_across_intents(
    project: Path, write_intent, patch_providers
):
    """Multiple bad active intents each show up in ``errors``."""
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent(
        "bad-one",
        evidence=[
            {
                "id": "x",
                "type": "case",
                "provider": "ghost",
                "query": "q",
                "expect": "p",
                "effort": "medium",
            }
        ],
    )
    write_intent("bad-two", evidence=[], constraints=[])
    res = preflight(project)
    assert res.valid is False
    assert set(res.errors.keys()) == {"bad-one", "bad-two"}


def test_preflight_on_missing_intents_dir(project: Path):
    """A project with no intents dir is trivially valid (nothing to validate)."""
    # Remove the intents subfolder
    import shutil
    shutil.rmtree(project / ".i2e" / "intents")
    res = preflight(project)
    assert res.valid is True
    assert res.errors == {}


def test_preflight_failed_exception_message_lists_caps(
    project: Path, write_intent, patch_providers
):
    """Smoke-check ``PreflightFailed.__init__`` renders a multi-line message."""
    from i2e_core.orchestrator import PreflightFailed

    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent("bad-empty", evidence=[], constraints=[])
    res = preflight(project)
    exc = PreflightFailed(res)
    msg = str(exc)
    assert "bad-empty" in msg
    assert "preflight failed" in msg
