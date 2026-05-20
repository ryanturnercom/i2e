"""Tests for the report-rename-attempts-to-retries capability.

The user-facing label in the report next to each item must read
``retries`` (because the counter only ticks on fail/unmet/trending, i.e.
spent retry budget) — but the persisted field name on ``ItemVerdict``
stays ``attempts_used`` so existing ``current.yaml`` files on disk
continue to parse.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from i2e_core.evidence import CurrentEvidence, ItemVerdict, write_current
from i2e_core.report import render, render_to_string


_INTENT = """---
capability: {name}
created: 2026-05-19
updated: 2026-05-19
version: 1
status: active
watcher: '@me'
---

# {name}

## Evidence of success

- id: case-a
  type: case
  provider: pytest
  query: tests/test_{name_us}.py
  expect: passes
  effort: medium

## Constraints

"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    for sub in ("context", "intents", "evidence", "pending", "logs"):
        (tmp_path / ".i2e" / sub).mkdir(parents=True, exist_ok=True)
    return tmp_path


def _write_intent(project: Path, name: str) -> Path:
    p = project / ".i2e" / "intents" / f"{name}.md"
    p.write_text(
        _INTENT.format(name=name, name_us=name.replace("-", "_")),
        encoding="utf-8",
    )
    return p


def _write_current(project: Path, name: str, verdict: str) -> None:
    cur = CurrentEvidence(
        capability=name,
        last_run="2026-05-20-aaa000",
        intent_version=1,
        items={
            "case-a": ItemVerdict(
                verdict=verdict,
                attempts_used=2,
                last_observed=datetime.now(timezone.utc),
                raw={},
            )
        },
    )
    write_current(project, cur)


def test_rendered_report_uses_retries_label(project: Path) -> None:
    _write_intent(project, "alpha")
    _write_current(project, "alpha", "pass")
    html = render_to_string(project)
    # User-facing label is "retries".
    assert "retries" in html
    # And the old label is gone — the rename is the whole point.
    assert "attempts" not in html.replace("attempts_used", "").replace(
        "max_attempts", ""
    )


def test_persisted_attempts_used_field_name_unchanged() -> None:
    # The persisted field name must NOT have been renamed — only the
    # user-facing label moved. This is the load-bearing detail: existing
    # current.yaml files on disk would fail to parse otherwise.
    v = ItemVerdict(
        verdict="pass",
        attempts_used=0,
        last_observed=datetime.now(timezone.utc),
        raw={},
    )
    assert hasattr(v, "attempts_used")
    assert v.attempts_used == 0
    # Round-trip through model_dump must still emit attempts_used.
    dumped = v.model_dump(mode="json")
    assert "attempts_used" in dumped
    assert "retries_used" not in dumped


def test_report_renders_without_template_error(project: Path) -> None:
    # Two intents, both with one item, one passing and one failing —
    # exercises both render paths through the same template.
    _write_intent(project, "alpha")
    _write_intent(project, "beta")
    _write_current(project, "alpha", "pass")
    _write_current(project, "beta", "fail")
    p = render(project)
    assert p.exists()
    text = p.read_text(encoding="utf-8")
    # Renders without raising and produces non-trivial HTML.
    assert text.startswith("<!DOCTYPE html>")
    assert "alpha" in text
    assert "beta" in text
