"""Tests for `i2e_core.config`."""

from __future__ import annotations

from pathlib import Path

import pytest

from i2e_core import config


def test_defaults_when_no_file(tmp_path: Path):
    # tmp_path has no .i2e/ — loader uses defaults
    cfg = config.load_config(tmp_path)
    assert cfg.defaults.case_effort == "medium"
    assert cfg.defaults.target_effort == "low"
    assert cfg.defaults.watcher == "@me"
    assert cfg.scheduler.cadence == "weekly"


def test_defaults_when_root_is_none():
    cfg = config.load_config(None)
    assert cfg.effort_tiers.case["medium"].max_attempts == 6


def test_partial_merge(tmp_path: Path):
    (tmp_path / ".i2e").mkdir()
    (tmp_path / ".i2e" / "config.yaml").write_text(
        "defaults:\n  watcher: '@team-x'\n", encoding="utf-8"
    )
    cfg = config.load_config(tmp_path)
    assert cfg.defaults.watcher == "@team-x"
    # other defaults preserved
    assert cfg.defaults.case_effort == "medium"
    assert cfg.effort_tiers.case["high"].max_attempts == 10


def test_resolve_max_attempts_case():
    cfg = config.default_config()
    assert config.resolve_max_attempts(cfg, "case", "medium") == 6
    assert config.resolve_max_attempts(cfg, "case", "lazy") == 0


def test_resolve_max_attempts_target():
    cfg = config.default_config()
    assert config.resolve_max_attempts(cfg, "target", "lazy") == 0
    assert config.resolve_max_attempts(cfg, "target", "high") == 5


def test_resolve_max_attempts_constraint_uses_case_map():
    cfg = config.default_config()
    # high under case map is 10; under target map is 5
    assert config.resolve_max_attempts(cfg, "constraint", "high") == 10


def test_resolve_max_attempts_invalid_effort():
    cfg = config.default_config()
    with pytest.raises(ValueError, match="Unknown effort"):
        config.resolve_max_attempts(cfg, "case", "sky-high")


def test_resolve_max_attempts_invalid_type():
    cfg = config.default_config()
    with pytest.raises(ValueError, match="Unknown item_type"):
        config.resolve_max_attempts(cfg, "bogus", "medium")  # type: ignore[arg-type]


def test_load_config_rejects_non_mapping(tmp_path: Path):
    (tmp_path / ".i2e").mkdir()
    (tmp_path / ".i2e" / "config.yaml").write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ValueError):
        config.load_config(tmp_path)


def test_serve_defaults():
    cfg = config.default_config()
    assert cfg.serve.port == 4230
    assert cfg.serve.open_browser is True


def test_serve_partial_override(tmp_path: Path):
    (tmp_path / ".i2e").mkdir()
    (tmp_path / ".i2e" / "config.yaml").write_text(
        "serve:\n  port: 9001\n  open_browser: false\n", encoding="utf-8"
    )
    cfg = config.load_config(tmp_path)
    assert cfg.serve.port == 9001
    assert cfg.serve.open_browser is False
    # Other sections still default
    assert cfg.defaults.case_effort == "medium"


def test_autoreload_defaults_off():
    # Auto-reload only earns its keep when dogfooding i2e on itself, so it
    # is opt-in: a normal install must not pay for a code watcher.
    assert config.default_config().serve.autoreload is False


def test_autoreload_partial_override(tmp_path: Path):
    (tmp_path / ".i2e").mkdir()
    (tmp_path / ".i2e" / "config.yaml").write_text(
        "serve:\n  autoreload: true\n", encoding="utf-8"
    )
    cfg = config.load_config(tmp_path)
    assert cfg.serve.autoreload is True
    # Untouched serve keys keep their defaults.
    assert cfg.serve.port == 4230


def test_watch_defaults():
    cfg = config.default_config()
    assert cfg.watch.max_concurrent == 4
    assert cfg.watch.debounce_ms == 400


def test_watch_partial_override(tmp_path: Path):
    (tmp_path / ".i2e").mkdir()
    (tmp_path / ".i2e" / "config.yaml").write_text(
        "watch:\n  max_concurrent: 8\n", encoding="utf-8"
    )
    cfg = config.load_config(tmp_path)
    assert cfg.watch.max_concurrent == 8
    # Untouched watch keys keep their defaults.
    assert cfg.watch.debounce_ms == 400
    # Other sections still default.
    assert cfg.serve.port == 4230
