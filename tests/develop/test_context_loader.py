"""Tests for `i2e_core.context`."""

from __future__ import annotations

from pathlib import Path

from i2e_core import context


def test_list_context_files_empty_when_dir_empty(develop_project: Path):
    assert context.list_context_files(develop_project) == []


def test_list_context_files_missing_dir_is_empty(tmp_path: Path):
    # No `.i2e/` at all — list_context_files should not raise.
    assert context.list_context_files(tmp_path) == []


def test_list_context_files_sorted(develop_project_with_context: Path):
    files = context.list_context_files(develop_project_with_context)
    # Sorted alphabetically by path; ARCHITECTURE.md sorts before DESIGN.md.
    names = [p.name for p in files]
    assert names == sorted(names)
    assert "ARCHITECTURE.md" in names
    assert "DESIGN.md" in names


def test_list_context_files_recursive(develop_project: Path):
    nested = develop_project / ".i2e" / "context" / "sub"
    nested.mkdir(parents=True)
    (nested / "child.md").write_text("# Child\n", encoding="utf-8")
    (develop_project / ".i2e" / "context" / "top.md").write_text(
        "# Top\n", encoding="utf-8"
    )
    files = context.list_context_files(develop_project)
    rels = sorted(p.relative_to(
        develop_project / ".i2e" / "context"
    ).as_posix() for p in files)
    assert rels == ["sub/child.md", "top.md"]


def test_load_context_empty_returns_empty(develop_project: Path):
    assert context.load_context(develop_project) == {}


def test_load_context_returns_all_when_under_budget(
    develop_project_with_context: Path,
):
    loaded = context.load_context(develop_project_with_context)
    assert set(loaded.keys()) == {"ARCHITECTURE.md", "DESIGN.md"}
    for body in loaded.values():
        assert body  # non-empty


def test_load_context_truncates_at_document_boundary(
    develop_project: Path,
):
    base = develop_project / ".i2e" / "context"
    big = "x" * 1000
    (base / "a.md").write_text(big, encoding="utf-8")
    (base / "b.md").write_text(big, encoding="utf-8")
    (base / "c.md").write_text(big, encoding="utf-8")

    # Budget fits ~2 files. The third must be omitted entirely (not partial).
    loaded = context.load_context(develop_project, max_chars=2500)
    total = sum(len(v) for v in loaded.values())
    assert total <= 2500
    # No partial documents — every value is exactly 1000 chars.
    assert all(len(v) == 1000 for v in loaded.values())
    assert len(loaded) == 2
    assert set(loaded.keys()) == {"a.md", "b.md"}


def test_load_context_skips_oversized_file(develop_project: Path):
    base = develop_project / ".i2e" / "context"
    (base / "huge.md").write_text("x" * 5000, encoding="utf-8")
    loaded = context.load_context(develop_project, max_chars=1000)
    assert loaded == {}


def test_load_context_logs_truncation_warning(
    develop_project: Path, caplog
):
    base = develop_project / ".i2e" / "context"
    (base / "a.md").write_text("x" * 800, encoding="utf-8")
    (base / "b.md").write_text("x" * 800, encoding="utf-8")
    with caplog.at_level("WARNING", logger="i2e_core.context"):
        context.load_context(develop_project, max_chars=1000)
    assert any("truncated" in rec.message for rec in caplog.records)


def test_context_summary_empty(develop_project: Path):
    assert context.context_summary(develop_project) == ""


def test_context_summary_uses_first_heading(
    develop_project_with_context: Path,
):
    summary = context.context_summary(develop_project_with_context)
    lines = summary.splitlines()
    # One line per file, sorted.
    assert len(lines) == 2
    assert lines[0].startswith("ARCHITECTURE.md: ")
    assert "Architecture" in lines[0]
    assert lines[1].startswith("DESIGN.md: ")
    assert "Design notes" in lines[1]


def test_context_summary_first_line_when_no_heading(develop_project: Path):
    base = develop_project / ".i2e" / "context"
    (base / "no-heading.md").write_text(
        "just a plain first line\nsecond line\n", encoding="utf-8"
    )
    summary = context.context_summary(develop_project)
    assert summary == "no-heading.md: just a plain first line"


def test_context_summary_empty_file(develop_project: Path):
    base = develop_project / ".i2e" / "context"
    (base / "blank.md").write_text("", encoding="utf-8")
    summary = context.context_summary(develop_project)
    assert summary == "blank.md:"
