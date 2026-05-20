"""Tests for path-suggestion helpers in `i2e_core.develop`."""

from __future__ import annotations

from pathlib import Path

from i2e_core import develop, intent
from i2e_core.intent_template import default_capability


def test_suggested_src_paths_replaces_hyphens_with_underscores():
    cap = default_capability("shorten-url", "@me")
    paths = develop.suggested_src_paths(cap)
    assert paths == [Path("src/shorten_url/__init__.py")]


def test_suggested_src_paths_single_word_capability():
    cap = default_capability("billing", "@me")
    paths = develop.suggested_src_paths(cap)
    assert paths == [Path("src/billing/__init__.py")]


def test_suggested_src_paths_multi_hyphen():
    cap = default_capability("really-long-slug-here", "@me")
    paths = develop.suggested_src_paths(cap)
    assert paths == [Path("src/really_long_slug_here/__init__.py")]


def test_suggested_test_paths_pytest_nodeid():
    item = intent.EvidenceItem(
        id="a", type="case", provider="pytest",
        query="tests/test_shorten.py::test_returns_7_char_code",
        expect="passes",
    )
    assert develop.suggested_test_paths(item) == Path("tests/test_shorten.py")


def test_suggested_test_paths_pytest_no_nodeid():
    """A bare file path (no ``::test_xxx``) is also accepted."""
    item = intent.EvidenceItem(
        id="a", type="case", provider="pytest",
        query="tests/test_full_file.py",
        expect="passes",
    )
    assert develop.suggested_test_paths(item) == Path("tests/test_full_file.py")


def test_suggested_test_paths_constraint():
    cn = intent.Constraint(
        id="c", provider="pytest",
        query="tests/adversarial/test_open_redirect.py::test_blocked",
        expect="passes",
    )
    assert develop.suggested_test_paths(cn) == Path(
        "tests/adversarial/test_open_redirect.py"
    )


def test_suggested_test_paths_non_pytest_returns_none():
    item = intent.EvidenceItem(
        id="lat", type="target", provider="datadog",
        query="redirect_latency{quantile=0.95}",
        expect="<50ms",
        window="5m",
    )
    assert develop.suggested_test_paths(item) is None


def test_suggested_test_paths_human_returns_none():
    item = intent.EvidenceItem(
        id="brand", type="target", provider="human",
        query="Open the app and see if it feels good.",
        expect="yes",
    )
    assert develop.suggested_test_paths(item) is None


def test_develop_summary_first_run():
    diff = develop.DevelopDiff(
        prior_version=None,
        current_version=1,
        new_items=["a", "b"],
    )
    s = develop.develop_summary(diff, [Path("src/a/__init__.py")])
    assert "first develop" in s
    assert "new=2" in s
    assert "changed=0" in s
    assert "files_touched=1" in s
    assert "\n" not in s


def test_develop_summary_version_bump():
    diff = develop.DevelopDiff(
        prior_version=1,
        current_version=2,
        new_items=["new-one"],
        changed_items=["a", "b"],
        removed_items=["dead"],
    )
    s = develop.develop_summary(
        diff, [Path("src/x.py"), Path("tests/test_x.py")]
    )
    assert "intent v1 -> v2" in s
    assert "new=1" in s
    assert "changed=2" in s
    assert "removed=1" in s
    assert "files_touched=2" in s


def test_develop_summary_no_version_bump():
    diff = develop.DevelopDiff(
        prior_version=2,
        current_version=2,
    )
    s = develop.develop_summary(diff, [])
    assert "no version bump" in s
    assert "files_touched=0" in s
