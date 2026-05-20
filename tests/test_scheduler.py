"""Tests for the scheduler integration helper."""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest

from i2e_core.scheduler import (
    _main,
    detect_claude_code,
    os_scheduler_templates,
    suggest_registration,
)


def test_detect_claude_code_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "i2e_core.scheduler.shutil.which",
        lambda name: "/usr/local/bin/claude" if name == "claude" else None,
    )
    assert detect_claude_code() is True


def test_detect_claude_code_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "i2e_core.scheduler.shutil.which", lambda name: None
    )
    assert detect_claude_code() is False


def test_suggest_registration_default_cadence(tmp_path: Path) -> None:
    cmd = suggest_registration(tmp_path)
    assert cmd.startswith('claude /schedule "Run i2e"')
    assert str(tmp_path.resolve()) in cmd
    assert "--cadence" in cmd
    # Default cadence from default_config is "weekly"
    assert "weekly" in cmd


def test_suggest_registration_override_cadence(tmp_path: Path) -> None:
    cmd = suggest_registration(tmp_path, cadence="hourly")
    assert "hourly" in cmd


def test_suggest_registration_picks_up_config(tmp_path: Path) -> None:
    (tmp_path / ".i2e").mkdir()
    (tmp_path / ".i2e" / "config.yaml").write_text(
        "scheduler:\n  cadence: daily\n", encoding="utf-8"
    )
    cmd = suggest_registration(tmp_path)
    assert "daily" in cmd


def test_os_scheduler_templates_keys(tmp_path: Path) -> None:
    tpl = os_scheduler_templates(tmp_path)
    assert set(tpl.keys()) == {"windows", "launchd", "cron"}
    for v in tpl.values():
        assert isinstance(v, str)
        assert v.strip()  # non-empty


def test_os_scheduler_templates_contain_project_path(tmp_path: Path) -> None:
    tpl = os_scheduler_templates(tmp_path)
    root_str = str(tmp_path.resolve())
    for key in ("windows", "launchd", "cron"):
        assert root_str in tpl[key], f"{key} template missing project path"


def test_os_scheduler_templates_cadence_daily(tmp_path: Path) -> None:
    tpl = os_scheduler_templates(tmp_path, cadence="daily")
    # cron daily default is "0 9 * * *"
    assert "0 9 * * *" in tpl["cron"]
    # Windows daily flag includes 'Daily'
    assert "Daily" in tpl["windows"]


def test_os_scheduler_templates_unknown_cadence_falls_back(tmp_path: Path) -> None:
    """Unknown cadence should not crash — fall back to weekly."""
    tpl = os_scheduler_templates(tmp_path, cadence="invalid")
    assert "0 9 * * 1" in tpl["cron"]


def test_cli_suggest_prints_sections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "i2e_core.scheduler.shutil.which", lambda name: None
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = _main(["suggest", "--root", str(tmp_path)])
    assert rc == 0
    out = buf.getvalue()
    assert "Windows Task Scheduler" in out
    assert "launchd" in out
    assert "cron" in out
    assert "Claude Code CLI detected: False" in out


def test_cli_suggest_with_claude_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "i2e_core.scheduler.shutil.which",
        lambda name: "/usr/local/bin/claude" if name == "claude" else None,
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = _main(["suggest", "--root", str(tmp_path)])
    assert rc == 0
    out = buf.getvalue()
    assert "Suggested registration:" in out
    assert "claude /schedule" in out
