"""Deep-link helper tests (file:// vs http://)."""

from __future__ import annotations

import re
from pathlib import Path

from i2e_core.report.links import (
    deep_link,
    link_capability,
    link_item,
    link_pending,
    link_tick,
)


def test_deep_link_with_serve_url(project: Path) -> None:
    (project / ".i2e" / ".serve.url").write_text(
        "http://127.0.0.1:54321/", encoding="utf-8"
    )
    assert deep_link(project, "#cap/alpha") == "http://127.0.0.1:54321/#cap/alpha"
    assert deep_link(project, "") == "http://127.0.0.1:54321/"


def test_deep_link_file_uri(project: Path) -> None:
    """Without a serve URL the link is a file:// URI to .i2e/report.html."""
    url = deep_link(project, "#cap/alpha")
    assert url.startswith("file:///")
    assert url.endswith("/.i2e/report.html#cap/alpha")
    # Windows absolute form should be present (drive letter colon).
    # On posix the path will start file:///root/... — either way it's absolute.
    assert ".i2e/report.html" in url


def test_link_helpers(project: Path) -> None:
    (project / ".i2e" / ".serve.url").write_text(
        "http://127.0.0.1:5555/", encoding="utf-8"
    )
    assert link_capability(project, "alpha") == "http://127.0.0.1:5555/#cap/alpha"
    assert (
        link_item(project, "alpha", "case-a")
        == "http://127.0.0.1:5555/#item/alpha/case-a"
    )
    assert (
        link_pending(project, "2026-05-19-alpha-case-a.yaml")
        == "http://127.0.0.1:5555/#pending/2026-05-19-alpha-case-a.yaml"
    )
    assert (
        link_tick(project, "2026-05-19-abc123")
        == "http://127.0.0.1:5555/#tick/2026-05-19-abc123"
    )


def test_deep_link_adds_hash_if_missing(project: Path) -> None:
    """Convenience: callers can omit the leading ``#``."""
    url = deep_link(project, "cap/alpha")
    assert "#cap/alpha" in url


def test_file_uri_is_windows_safe(project: Path, monkeypatch) -> None:
    """On Windows, ``Path.as_uri`` already produces ``file:///C:/...``.

    This test exercises the production code on the current platform and
    asserts the regex shape (three slashes, then a drive letter or path).
    """
    url = deep_link(project, "#cap/alpha")
    assert re.match(r"^file:///[A-Za-z]:/|^file:///\w", url) is not None
