"""Fixtures for tests of the `i2e-intent` skill helpers.

The save gate calls `installed_provider_names()`, which scans
`~/.claude/skills/` and `<cwd>/.claude/skills/`. To stay hermetic we
monkeypatch the gate module's reference to that function so the test
controls exactly which providers are "installed".
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pytest

from i2e_core import intent_save_gate
from i2e_core.provider.discovery import clear_cache


@pytest.fixture(autouse=True)
def _reset_provider_cache() -> None:
    clear_cache()
    yield
    clear_cache()


@pytest.fixture
def fake_skills_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Pretend ``pytest`` is the only installed provider.

    Replaces ``intent_save_gate.installed_provider_names`` with a stub that
    returns ``{"pytest"}`` regardless of arguments. Returns a tmp_path-based
    skills dir for tests that want to introspect it (not actually scanned).
    """
    skills_dir = tmp_path / ".claude" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / "i2e-provider-pytest").mkdir(parents=True, exist_ok=True)

    def _stub(extra_paths: Iterable[Path] | None = None) -> set[str]:
        return {"pytest"}

    monkeypatch.setattr(
        intent_save_gate, "installed_provider_names", _stub
    )
    return skills_dir


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """A minimal `.i2e/` skeleton under tmp_path, with no intents on disk."""
    for sub in ("context", "intents", "evidence", "pending", "logs"):
        (tmp_path / ".i2e" / sub).mkdir(parents=True, exist_ok=True)
    return tmp_path
