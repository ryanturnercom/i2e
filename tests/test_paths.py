"""Tests for `i2e_core.paths`."""

from __future__ import annotations

from pathlib import Path

import pytest

from i2e_core import paths


def test_find_root_from_subdir(project_root: Path):
    deep = project_root / "src" / "i2e_core"
    deep.mkdir(parents=True, exist_ok=True)
    assert paths.find_root(deep) == project_root


def test_find_root_from_root_itself(project_root: Path):
    assert paths.find_root(project_root) == project_root


def test_find_root_missing(tmp_path: Path):
    with pytest.raises(RuntimeError, match="i2e-intent"):
        paths.find_root(tmp_path)


def test_path_helpers(project_root: Path):
    assert paths.intents_dir(project_root).name == "intents"
    assert paths.evidence_dir(project_root, "x").parent.name == "evidence"
    assert paths.runs_dir(project_root, "x").name == "runs"
    assert paths.current_path(project_root, "x").name == "current.yaml"
    assert paths.pending_dir(project_root).name == "pending"
    assert paths.logs_dir(project_root).name == "logs"
    assert paths.context_dir(project_root).name == "context"
    assert paths.config_path(project_root).name == "config.yaml"
    assert paths.report_path(project_root).name == "report.html"
    assert paths.serve_url_path(project_root).name == ".serve.url"
