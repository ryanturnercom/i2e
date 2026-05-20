"""Smoke tests for ``i2e-provider-pytest``.

We invoke the real subprocess — the spec is "forced evidence", let's eat our
own dog food. The fixture pytest files live in ``./_fixtures/``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from i2e_core.intent import EvidenceItem
from i2e_core.provider import ProviderContext
from i2e_core.provider.discovery import (
    installed_provider_names,
    load_provider,
)

FIXTURE_DIR = Path(__file__).parent / "_fixtures"


def _make_item(query: str) -> EvidenceItem:
    return EvidenceItem(
        id="run-fixture",
        type="case",
        provider="pytest",
        query=query,
        expect="passes",
    )


def _seed_fixture_project(tmp_path: Path) -> Path:
    """Copy fixture test files into ``tmp_path/tests/`` so cwd resolves them."""
    dest = tmp_path / "tests"
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("passing_test.py", "failing_test.py"):
        shutil.copyfile(FIXTURE_DIR / name, dest / name)
    return dest


def test_discovery_picks_up_pytest(fake_skills_root: Path) -> None:
    names = installed_provider_names(extra_paths=[fake_skills_root])
    assert "pytest" in names


def test_load_pytest_returns_named_provider(fake_skills_root: Path) -> None:
    provider = load_provider("pytest", extra_paths=[fake_skills_root])
    assert provider.name == "pytest"
    assert callable(provider.invoke)


def test_pytest_provider_pass(fake_skills_root: Path, provider_ctx: ProviderContext) -> None:
    _seed_fixture_project(provider_ctx.root)
    provider = load_provider("pytest", extra_paths=[fake_skills_root])
    item = _make_item("tests/passing_test.py::test_passes")
    result = provider.invoke(item, provider_ctx)
    assert result.verdict == "pass", f"output was: {result.output}"


def test_pytest_provider_fail(fake_skills_root: Path, provider_ctx: ProviderContext) -> None:
    _seed_fixture_project(provider_ctx.root)
    provider = load_provider("pytest", extra_paths=[fake_skills_root])
    item = _make_item("tests/failing_test.py::test_fails")
    result = provider.invoke(item, provider_ctx)
    assert result.verdict == "fail"
    assert result.output, "fail output should not be empty"
    # The fail trace mentions the asserting line or "assert" keyword.
    assert "assert" in result.output.lower() or "fail" in result.output.lower()
