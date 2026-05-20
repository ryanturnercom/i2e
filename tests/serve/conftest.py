"""Shared fixtures for the serve tests."""

from __future__ import annotations

import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pytest

from i2e_core.evidence import CurrentEvidence, ItemVerdict, write_current


_INTENT_TEMPLATE = """---
capability: {name}
created: 2026-05-19
updated: 2026-05-19
version: {version}
status: active
watcher: '@me'
---

# {name}

Test capability for serve tests.

## Evidence of success

{evidence}

## Constraints

"""


def _render_block(items: list[dict]) -> str:
    if not items:
        return ""
    rendered: list[str] = []
    for it in items:
        lines: list[str] = []
        first = True
        for k, v in it.items():
            prefix = "- " if first else "  "
            first = False
            lines.append(f"{prefix}{k}: {v}")
        rendered.append("\n".join(lines))
    return "\n\n".join(rendered)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    for sub in ("context", "intents", "evidence", "pending", "logs"):
        (tmp_path / ".i2e" / sub).mkdir(parents=True, exist_ok=True)
    # Drop in one active capability so the rendered page has content.
    body = _INTENT_TEMPLATE.format(
        name="alpha",
        version=1,
        evidence=_render_block(
            [
                {
                    "id": "case-a",
                    "type": "case",
                    "provider": "pytest",
                    "query": "q",
                    "expect": "passes",
                    "effort": "medium",
                }
            ]
        ),
    )
    (tmp_path / ".i2e" / "intents" / "alpha.md").write_text(
        textwrap.dedent(body), encoding="utf-8"
    )
    cap = CurrentEvidence(
        capability="alpha",
        last_run="2026-05-19-aaa000",
        intent_version=1,
        items={
            "case-a": ItemVerdict(
                verdict="pass",
                attempts_used=0,
                last_observed=datetime.now(timezone.utc),
            )
        },
    )
    write_current(tmp_path, cap)
    return tmp_path
