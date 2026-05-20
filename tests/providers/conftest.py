"""Shared fixtures for provider tests.

We build a ``tmp_path/.claude/skills/`` tree by copying the two real provider
skills into it. That way the tests exercise the same loader path real users
will hit, but stay hermetic — every test gets a fresh skills dir.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from i2e_core.config import default_config
from i2e_core.provider import ProviderContext
from i2e_core.provider.discovery import clear_cache
from i2e_core.runid import new_run_id

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REAL_SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"


@pytest.fixture(autouse=True)
def _reset_provider_cache() -> None:
    """Ensure dynamic module loads are not cached between tests."""
    clear_cache()
    yield
    clear_cache()


@pytest.fixture
def fake_skills_root(tmp_path: Path) -> Path:
    """Copy the real provider skills into a ``tmp_path/.claude/skills/`` tree."""
    dst = tmp_path / ".claude" / "skills"
    dst.mkdir(parents=True, exist_ok=True)
    skill_names = (
        "i2e-provider-pytest",
        "i2e-provider-human",
        "i2e-provider-datadog",
        "i2e-provider-sentry",
        "i2e-provider-ga",
        "i2e-provider-survey",
    )
    for name in skill_names:
        src = REAL_SKILLS_DIR / name
        if src.exists():
            shutil.copytree(src, dst / name)
    return dst


@pytest.fixture
def provider_ctx(tmp_path: Path) -> ProviderContext:
    """A ``ProviderContext`` rooted at ``tmp_path`` with default config."""
    # Make sure .i2e/ exists so providers that write under it can do so.
    for sub in ("pending", "logs", "evidence", "intents", "context"):
        (tmp_path / ".i2e" / sub).mkdir(parents=True, exist_ok=True)
    return ProviderContext(
        root=tmp_path,
        capability="demo-capability",
        run_id=new_run_id(),
        cfg=default_config(),
    )
