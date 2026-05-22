"""Tests for project scaffolding (``i2e_core.init``)."""

from __future__ import annotations

import json
import stat
import sys

import pytest

from i2e_core.init import (
    SCRIPT_NAMES,
    _main,
    _script_bytes,
    init_project,
    scaffold_dirs,
)


def test_init_creates_full_layout(tmp_path):
    result = init_project(tmp_path)

    for d in scaffold_dirs(tmp_path):
        assert d.is_dir()
    assert set(result.created_dirs) == set(scaffold_dirs(tmp_path))
    assert result.changed is True


def test_init_copies_all_scripts(tmp_path):
    result = init_project(tmp_path)

    ldir = tmp_path / ".i2e"
    for name in SCRIPT_NAMES:
        dest = ldir / name
        assert dest.is_file()
        assert dest.read_bytes() == _script_bytes(name)
    assert {p.name for p in result.copied_scripts} == set(SCRIPT_NAMES)
    assert result.skipped == []


def test_scripts_have_lf_line_endings(tmp_path):
    init_project(tmp_path)
    for name in SCRIPT_NAMES:
        data = (tmp_path / ".i2e" / name).read_bytes()
        assert b"\r\n" not in data
        assert data.startswith(b"#!/usr/bin/env bash")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX exec bit")
def test_scripts_are_executable(tmp_path):
    init_project(tmp_path)
    for name in SCRIPT_NAMES:
        mode = (tmp_path / ".i2e" / name).stat().st_mode
        assert mode & stat.S_IXUSR


def test_init_is_idempotent(tmp_path):
    init_project(tmp_path)
    second = init_project(tmp_path)

    assert second.created_dirs == []
    assert second.copied_scripts == []
    assert {p.name for p in second.skipped} == set(SCRIPT_NAMES)
    assert second.changed is False


def test_init_preserves_existing_content(tmp_path):
    intents = tmp_path / ".i2e" / "intents"
    intents.mkdir(parents=True)
    keeper = intents / "foo.md"
    keeper.write_text("hand-authored", encoding="utf-8")

    init_project(tmp_path)

    assert keeper.read_text(encoding="utf-8") == "hand-authored"


def test_init_skips_modified_scripts_by_default(tmp_path):
    init_project(tmp_path)
    serve = tmp_path / ".i2e" / "start.sh"
    serve.write_text("# locally edited", encoding="utf-8")

    result = init_project(tmp_path)

    assert serve.read_text(encoding="utf-8") == "# locally edited"
    assert serve in result.skipped


def test_force_scripts_overwrites(tmp_path):
    init_project(tmp_path)
    serve = tmp_path / ".i2e" / "start.sh"
    serve.write_text("# locally edited", encoding="utf-8")

    result = init_project(tmp_path, force_scripts=True)

    assert serve.read_bytes() == _script_bytes("start.sh")
    assert serve in result.copied_scripts


def test_partial_layout_is_completed(tmp_path):
    # .i2e/ exists but its subdirs are missing.
    (tmp_path / ".i2e").mkdir()

    result = init_project(tmp_path)

    for d in scaffold_dirs(tmp_path):
        assert d.is_dir()
    # .i2e/ itself pre-existed, so it is not reported as created.
    assert (tmp_path / ".i2e") not in result.created_dirs
    assert (tmp_path / ".i2e" / "intents") in result.created_dirs


def test_cli_initialises_and_prints_json(tmp_path, capsys):
    rc = _main(["--root", str(tmp_path)])
    assert rc == 0

    out = json.loads(capsys.readouterr().out)
    assert out["root"] == str(tmp_path.resolve())
    assert len(out["copied_scripts"]) == len(SCRIPT_NAMES)
    for d in scaffold_dirs(tmp_path):
        assert d.is_dir()


def test_cli_force_scripts_flag(tmp_path, capsys):
    _main(["--root", str(tmp_path)])
    capsys.readouterr()
    serve = tmp_path / ".i2e" / "start.sh"
    serve.write_text("# edited", encoding="utf-8")

    rc = _main(["--root", str(tmp_path), "--force-scripts"])
    assert rc == 0
    assert serve.read_bytes() == _script_bytes("start.sh")
