"""Tests for `i2e_core.evidence`."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from i2e_core import evidence, paths


def _make_current() -> evidence.CurrentEvidence:
    return evidence.CurrentEvidence(
        capability="shorten-url",
        last_run="2026-05-19-a3f8c2",
        intent_version=1,
        items={
            "code-generated": evidence.ItemVerdict(
                verdict="pass",
                last_observed=datetime(2026, 5, 19, 14, 32, tzinfo=timezone.utc),
            ),
            "redirect-latency-p95": evidence.ItemVerdict(
                verdict="met",
                value="32ms",
                last_observed=datetime(2026, 5, 19, 14, 32, tzinfo=timezone.utc),
            ),
        },
    )


def _make_snap(run_id: str = "2026-05-19-a3f8c2") -> evidence.RunSnapshot:
    return evidence.RunSnapshot(
        run_id=run_id,
        capability="shorten-url",
        intent_version=1,
        collected_at=datetime(2026, 5, 19, 14, 32, tzinfo=timezone.utc),
        items={
            "code-generated": evidence.ItemVerdict(verdict="pass"),
        },
    )


def test_read_current_missing_returns_none(project_root: Path):
    assert evidence.read_current(project_root, "shorten-url") is None


def test_write_then_read_current(project_root: Path):
    cur = _make_current()
    evidence.write_current(project_root, cur)
    p = paths.current_path(project_root, cur.capability)
    assert p.exists()
    loaded = evidence.read_current(project_root, cur.capability)
    assert loaded == cur


def test_write_run_snapshot_then_list(project_root: Path):
    s1 = _make_snap("2026-05-01-aaa111")
    s2 = _make_snap("2026-05-19-bbb222")
    evidence.write_run_snapshot(project_root, s1)
    evidence.write_run_snapshot(project_root, s2)
    runs = evidence.list_runs(project_root, "shorten-url")
    assert [p.stem for p in runs] == ["2026-05-01-aaa111", "2026-05-19-bbb222"]


def test_write_run_snapshot_immutable(project_root: Path):
    s = _make_snap()
    evidence.write_run_snapshot(project_root, s)
    with pytest.raises(FileExistsError):
        evidence.write_run_snapshot(project_root, s)


def test_read_run_roundtrip(project_root: Path):
    s = _make_snap()
    p = evidence.write_run_snapshot(project_root, s)
    loaded = evidence.read_run(p)
    assert loaded == s


def test_list_runs_empty(project_root: Path):
    assert evidence.list_runs(project_root, "no-such-cap") == []


def test_write_current_creates_directory(tmp_path: Path):
    # no .i2e/evidence/<cap> exists yet
    (tmp_path / ".i2e").mkdir()
    cur = _make_current()
    evidence.write_current(tmp_path, cur)
    assert paths.current_path(tmp_path, cur.capability).exists()
