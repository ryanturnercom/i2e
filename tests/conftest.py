"""Shared pytest fixtures for the foundation tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def shorten_url_fixture() -> Path:
    return FIXTURES / "shorten-url.md"


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """Build a temporary project with a minimal `.i2e/` skeleton."""
    for sub in ("context", "intents", "evidence", "pending", "logs"):
        (tmp_path / ".i2e" / sub).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        FIXTURES / "shorten-url.md",
        tmp_path / ".i2e" / "intents" / "shorten-url.md",
    )
    return tmp_path
