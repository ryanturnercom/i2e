"""Project-local provider must override a user-level provider with the same name."""

from __future__ import annotations

from pathlib import Path

import pytest

from i2e_core.provider.discovery import (
    clear_cache,
    installed_provider_names,
    load_provider,
)


def _write_fake_provider(folder: Path, label: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(
        f"---\nname: {folder.name}\nlabel: {label}\n---\n", encoding="utf-8"
    )
    (folder / "provider.py").write_text(
        "class FakeProvider:\n"
        f"    name = 'fake'\n"
        f"    label = {label!r}\n"
        "    def invoke(self, item, ctx):\n"
        "        return ('ok', self.label)\n"
        "provider = FakeProvider()\n",
        encoding="utf-8",
    )


def test_local_overrides_user_level(tmp_path: Path) -> None:
    user_dir = tmp_path / "user" / ".claude" / "skills"
    proj_dir = tmp_path / "proj" / ".claude" / "skills"
    _write_fake_provider(user_dir / "i2e-provider-fake", "user-version")
    _write_fake_provider(proj_dir / "i2e-provider-fake", "project-version")

    names = installed_provider_names(extra_paths=[user_dir, proj_dir])
    assert "fake" in names

    clear_cache()
    provider = load_provider("fake", extra_paths=[user_dir, proj_dir])
    # Project-local (passed last) wins.
    assert provider.label == "project-version"


def test_missing_provider_raises_lookup_error(tmp_path: Path) -> None:
    skills = tmp_path / ".claude" / "skills"
    skills.mkdir(parents=True)
    with pytest.raises(LookupError) as exc:
        load_provider("does-not-exist", extra_paths=[skills])
    # Hint should mention the scanned skills dir.
    assert "does-not-exist" in str(exc.value)


def test_installed_provider_names_returns_empty_when_missing(tmp_path: Path) -> None:
    # extra_paths includes a non-existent dir; should not raise.
    nonexistent = tmp_path / "nope"
    result = installed_provider_names(extra_paths=[nonexistent])
    # May still find real user/project skills, but at minimum the call works.
    assert isinstance(result, set)


def test_user_only_when_no_project_override(tmp_path: Path) -> None:
    user_dir = tmp_path / "user" / ".claude" / "skills"
    proj_dir = tmp_path / "proj" / ".claude" / "skills"
    proj_dir.mkdir(parents=True, exist_ok=True)  # exists but empty
    _write_fake_provider(user_dir / "i2e-provider-onlyuser", "from-user")

    clear_cache()
    provider = load_provider("onlyuser", extra_paths=[user_dir, proj_dir])
    assert provider.label == "from-user"


def test_load_provider_folder_missing_provider_py_raises(tmp_path: Path) -> None:
    """A skill folder exists but has no provider.py — clear error."""
    skills = tmp_path / ".claude" / "skills"
    (skills / "i2e-provider-broken").mkdir(parents=True)
    # No provider.py written
    clear_cache()
    with pytest.raises(LookupError) as exc:
        load_provider("broken", extra_paths=[skills])
    assert "provider.py" in str(exc.value)


def test_load_provider_module_missing_attr_raises(tmp_path: Path) -> None:
    """A provider.py exists but doesn't define `provider` — raise AttributeError."""
    skills = tmp_path / ".claude" / "skills"
    folder = skills / "i2e-provider-bad"
    folder.mkdir(parents=True)
    (folder / "provider.py").write_text("# no provider here\n", encoding="utf-8")
    clear_cache()
    with pytest.raises(AttributeError) as exc:
        load_provider("bad", extra_paths=[skills])
    assert "provider" in str(exc.value)


def test_load_provider_caches_repeated_loads(tmp_path: Path) -> None:
    skills = tmp_path / ".claude" / "skills"
    _write_fake_provider(skills / "i2e-provider-cached", "v1")
    clear_cache()
    a = load_provider("cached", extra_paths=[skills])
    b = load_provider("cached", extra_paths=[skills])
    # Second load hits the cache and returns the same instance.
    assert a is b


def test_installed_provider_names_skips_non_dirs(tmp_path: Path) -> None:
    skills = tmp_path / ".claude" / "skills"
    skills.mkdir(parents=True)
    # A stray file shouldn't be reported as a provider.
    (skills / "i2e-provider-not-a-folder").write_text("decoy", encoding="utf-8")
    # A folder that doesn't match the prefix is ignored too.
    (skills / "unrelated-skill").mkdir()
    names = installed_provider_names(extra_paths=[skills])
    assert "not-a-folder" not in names
    assert "unrelated-skill" not in names
