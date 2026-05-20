"""Shared fixtures for the adapt tests.

Builds a temporary ``.i2e/`` project with a parameterizable intent +
``current.yaml``. Tests mostly want to dial verdicts and ``attempts_used``
per-item, so the helpers below are dict-driven.
"""

from __future__ import annotations

import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pytest

from i2e_core.evidence import CurrentEvidence, ItemVerdict, RunSnapshot, write_current
from i2e_core.evidence import write_run_snapshot


_INTENT_TEMPLATE = """---
capability: {name}
created: 2026-05-19
updated: 2026-05-19
version: {version}
status: active
watcher: '@me'
---

# {name}

Demo capability used in adapt tests.

## Evidence of success

{evidence}

## Constraints

{constraints}
"""


def _render_block(items: list[dict]) -> str:
    if not items:
        return ""
    out: list[str] = []
    for it in items:
        lines: list[str] = []
        first = True
        for k, v in it.items():
            prefix = "- " if first else "  "
            first = False
            lines.append(f"{prefix}{k}: {v}")
        out.append("\n".join(lines))
    return "\n\n".join(out)


def _write_intent_file(
    root: Path,
    name: str,
    evidence: list[dict],
    constraints: list[dict] | None = None,
    version: int = 1,
) -> Path:
    body = _INTENT_TEMPLATE.format(
        name=name,
        version=version,
        evidence=_render_block(evidence),
        constraints=_render_block(constraints or []),
    )
    target = root / ".i2e" / "intents" / f"{name}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(textwrap.dedent(body), encoding="utf-8")
    return target


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Bare ``.i2e/`` skeleton at ``tmp_path``."""
    for sub in ("context", "intents", "evidence", "pending", "logs"):
        (tmp_path / ".i2e" / sub).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def write_intent(project: Path) -> Callable[..., Path]:
    """Factory: ``write_intent(name, evidence=[...], constraints=[...], version=N)``."""

    def _factory(
        name: str,
        evidence: list[dict] | None = None,
        constraints: list[dict] | None = None,
        version: int = 1,
    ) -> Path:
        return _write_intent_file(
            project,
            name,
            evidence or [],
            constraints,
            version=version,
        )

    return _factory


@pytest.fixture
def write_current_for(project: Path) -> Callable[..., Path]:
    """Factory: write a ``current.yaml`` for a capability.

    ``items`` is a mapping ``item_id -> dict(verdict=..., attempts_used=...,
    value=...)``.
    """

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


@pytest.fixture
def write_run_for(project: Path) -> Callable[..., Path]:
    """Factory: write a run snapshot for a capability."""

    def _factory(
        capability: str,
        run_id: str,
        items: dict[str, dict[str, Any]],
        intent_version: int = 1,
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
                raw=payload.get("raw", {}),
            )
        snap = RunSnapshot(
            run_id=run_id,
            capability=capability,
            intent_version=intent_version,
            collected_at=datetime.now(timezone.utc),
            items=items_models,
        )
        return write_run_snapshot(project, snap)

    return _factory
