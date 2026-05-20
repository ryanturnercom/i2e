"""Shared fixtures for tests/report and tests/serve."""

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
status: {status}
watcher: '@me'
---

# {name}

Test capability.

## Evidence of success

{evidence}

## Constraints

{constraints}
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
    return tmp_path


@pytest.fixture
def write_intent(project: Path) -> Callable[..., Path]:
    def _factory(
        name: str,
        evidence: list[dict] | None = None,
        constraints: list[dict] | None = None,
        version: int = 1,
        status: str = "active",
    ) -> Path:
        body = _INTENT_TEMPLATE.format(
            name=name,
            version=version,
            status=status,
            evidence=_render_block(evidence or []),
            constraints=_render_block(constraints or []),
        )
        target = project / ".i2e" / "intents" / f"{name}.md"
        target.write_text(textwrap.dedent(body), encoding="utf-8")
        return target

    return _factory


@pytest.fixture
def write_current_for(project: Path) -> Callable[..., Path]:
    def _factory(
        capability: str,
        items: dict[str, dict[str, Any]],
        intent_version: int = 1,
        last_run: str = "2026-05-19-aaa000",
    ) -> Path:
        items_models: dict[str, ItemVerdict] = {}
        for item_id, payload in items.items():
            items_models[item_id] = ItemVerdict(
                verdict=payload["verdict"],
                value=payload.get("value"),
                attempts_used=payload.get("attempts_used", 0),
                last_observed=payload.get(
                    "last_observed", datetime.now(timezone.utc)
                ),
                pending=payload.get("pending"),
                raw=payload.get("raw", {}),
            )
        cap = CurrentEvidence(
            capability=capability,
            last_run=last_run,
            intent_version=intent_version,
            items=items_models,
        )
        return write_current(project, cap)

    return _factory
