"""Fixtures for the develop-skill tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def develop_project(tmp_path: Path) -> Path:
    """A `.i2e/` skeleton with the shorten-url fixture intent installed."""
    for sub in ("context", "intents", "evidence", "pending", "logs"):
        (tmp_path / ".i2e" / sub).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        FIXTURES / "shorten-url.md",
        tmp_path / ".i2e" / "intents" / "shorten-url.md",
    )
    return tmp_path


@pytest.fixture
def develop_project_with_context(develop_project: Path) -> Path:
    """`develop_project` plus seeded ARCHITECTURE.md / DESIGN.md context."""
    src_dir = FIXTURES / "context_seed"
    dst_dir = develop_project / ".i2e" / "context"
    for src in src_dir.iterdir():
        shutil.copyfile(src, dst_dir / src.name)
    return develop_project
