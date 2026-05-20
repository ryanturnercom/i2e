"""Smoke tests for ``i2e-provider-human`` + the pending-file IO layer."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from i2e_core.intent import EvidenceItem
from i2e_core.paths import logs_dir, pending_dir
from i2e_core.pending import (
    PendingFile,
    archive_pending,
    list_open_pending,
    list_resolved_pending,
    pending_filename,
    read_pending,
    write_pending,
)
from i2e_core.provider import AsyncResult, ProviderContext
from i2e_core.provider.discovery import (
    installed_provider_names,
    load_provider,
)


def _make_item(item_id: str = "human-1") -> EvidenceItem:
    return EvidenceItem(
        id=item_id,
        type="case",
        provider="human",
        query="Did this feel right?",
        expect="yes",
    )


# ---------- pending IO ----------


def test_pending_filename_format() -> None:
    when = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)
    fname = pending_filename("demo-capability", "human-1", when)
    assert fname == "2026-05-19-demo-capability-human-1.yaml"


def test_pending_round_trip(tmp_path: Path) -> None:
    (tmp_path / ".i2e").mkdir()
    pf = PendingFile(
        kind="human_evaluation",
        capability="demo-cap",
        item_id="some-item",
        asked_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
        ask="Confirm vibe",
        expect="yes",
        verdict_options=["yes", "no", "partial"],
    )
    path = write_pending(tmp_path, pf)
    assert path.exists()
    loaded = read_pending(path)
    assert loaded.capability == "demo-cap"
    assert loaded.item_id == "some-item"
    assert loaded.status == "open"
    assert loaded.verdict_options == ["yes", "no", "partial"]
    assert loaded.asked_at == datetime(2026, 5, 19, tzinfo=timezone.utc)


def test_write_pending_refuses_duplicate(tmp_path: Path) -> None:
    pf = PendingFile(
        kind="human_evaluation",
        capability="demo",
        item_id="dup",
        asked_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
        ask="?",
    )
    write_pending(tmp_path, pf)
    with pytest.raises(FileExistsError):
        write_pending(tmp_path, pf)


def test_list_open_vs_resolved(tmp_path: Path) -> None:
    open_pf = PendingFile(
        kind="human_evaluation",
        capability="cap",
        item_id="open-item",
        asked_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
        ask="?",
    )
    resolved_pf = PendingFile(
        status="resolved",
        kind="human_evaluation",
        capability="cap",
        item_id="resolved-item",
        asked_at=datetime(2026, 5, 18, tzinfo=timezone.utc),
        ask="?",
        resolution="yes",
    )
    write_pending(tmp_path, open_pf)
    write_pending(tmp_path, resolved_pf)
    open_paths = list_open_pending(tmp_path)
    resolved_paths = list_resolved_pending(tmp_path)
    assert len(open_paths) == 1
    assert len(resolved_paths) == 1
    assert "open-item" in open_paths[0].name
    assert "resolved-item" in resolved_paths[0].name


def test_archive_pending_moves_to_logs(tmp_path: Path) -> None:
    pf = PendingFile(
        kind="human_evaluation",
        capability="cap",
        item_id="archive-me",
        asked_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
        ask="?",
    )
    src = write_pending(tmp_path, pf)
    assert src.exists()
    dest = archive_pending(tmp_path, src)
    assert dest.exists()
    assert not src.exists()
    assert dest.parent == logs_dir(tmp_path)


def test_archive_pending_missing_source(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        archive_pending(tmp_path, tmp_path / ".i2e" / "pending" / "nope.yaml")


def test_list_pending_skips_unparseable(tmp_path: Path) -> None:
    pdir = pending_dir(tmp_path)
    pdir.mkdir(parents=True)
    # A bogus file shouldn't crash listing.
    (pdir / "broken.yaml").write_text("this is: not a pending file\nstray: keys\n", encoding="utf-8")
    assert list_open_pending(tmp_path) == []
    assert list_resolved_pending(tmp_path) == []


def test_list_pending_returns_empty_when_dir_missing(tmp_path: Path) -> None:
    # No `.i2e/pending` directory at all.
    assert list_open_pending(tmp_path) == []
    assert list_resolved_pending(tmp_path) == []


def test_pending_filename_default_when_no_datetime() -> None:
    # When `when` is None, current UTC date is used.
    fname = pending_filename("cap", "id")
    assert fname.endswith("-cap-id.yaml")
    assert len(fname.split("-")) >= 5  # YYYY MM DD cap id (kebab parts)


# ---------- discovery + provider invocation ----------


def test_discovery_picks_up_human(fake_skills_root: Path) -> None:
    names = installed_provider_names(extra_paths=[fake_skills_root])
    assert "human" in names


def test_load_human_returns_named_provider(fake_skills_root: Path) -> None:
    provider = load_provider("human", extra_paths=[fake_skills_root])
    assert provider.name == "human"


def test_human_first_invocation_writes_pending(
    fake_skills_root: Path, provider_ctx: ProviderContext
) -> None:
    provider = load_provider("human", extra_paths=[fake_skills_root])
    result = provider.invoke(_make_item("subjective-1"), provider_ctx)
    assert isinstance(result, AsyncResult)
    assert result.verdict == "awaiting_human"
    expected_basename_substr = "demo-capability-subjective-1.yaml"
    assert result.pending.endswith(expected_basename_substr)
    written = pending_dir(provider_ctx.root) / result.pending
    assert written.exists()
    pf = read_pending(written)
    assert pf.status == "open"
    assert pf.kind == "human_evaluation"
    assert pf.ask == "Did this feel right?"


def test_human_second_invocation_raises(
    fake_skills_root: Path, provider_ctx: ProviderContext
) -> None:
    provider = load_provider("human", extra_paths=[fake_skills_root])
    item = _make_item("dup-subj")
    provider.invoke(item, provider_ctx)
    with pytest.raises(FileExistsError):
        provider.invoke(item, provider_ctx)
