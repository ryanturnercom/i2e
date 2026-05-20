"""Shared fixtures for the orchestrator tests.

The orchestrator weaves together every prior epic, so the fixtures here mirror
what those epics' tests built — a tmp ``.i2e/`` skeleton, an intent writer,
``current.yaml`` writer, and a fake-provider injector (the orchestrator calls
``evidence_runner.run`` which in turn loads providers).
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pytest

from i2e_core.evidence import CurrentEvidence, ItemVerdict, write_current
from i2e_core.provider import (
    CaseResult,
    ProviderContext,
    ProviderResult,
    TargetResult,
)


# ---------- Fake provider plumbing (mirrors tests/evidence/conftest.py) ----------


@dataclass
class FakeProvider:
    name: str
    behavior: Callable[[object, ProviderContext], ProviderResult]

    def invoke(self, item, ctx: ProviderContext) -> ProviderResult:
        return self.behavior(item, ctx)


def always_pass() -> Callable[[object, ProviderContext], CaseResult]:
    return lambda item, ctx: CaseResult(verdict="pass", output="ok")


def always_fail(output: str = "boom") -> Callable[[object, ProviderContext], CaseResult]:
    return lambda item, ctx: CaseResult(verdict="fail", output=output)


def target_met(value: str = "ok") -> Callable[[object, ProviderContext], TargetResult]:
    return lambda item, ctx: TargetResult(
        value=value, met="met", observed_at=datetime.now(timezone.utc)
    )


# ---------- Intent writer ----------


_INTENT_TEMPLATE = """---
capability: {name}
created: 2026-05-19
updated: 2026-05-19
version: {version}
status: {status}
watcher: '@me'
---

# {name}

Orchestrator-test capability.

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
    """``write_intent(name, evidence=[...], constraints=[...], version=N, status='active')``."""

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
    """Factory: ``write_current_for(capability, items={id: {verdict, attempts_used, ...}})``."""

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
def patch_providers(monkeypatch: pytest.MonkeyPatch) -> Callable[[dict[str, FakeProvider]], None]:
    """Install fake providers visible to both the orchestrator's preflight
    (``installed_provider_names``) AND the evidence runner (``load_provider``).
    """

    def _install(providers: dict[str, FakeProvider]) -> None:
        names = set(providers.keys())

        def fake_load(name: str, extra_paths=None):
            if name not in providers:
                raise LookupError(f"no fake provider for {name!r}")
            return providers[name]

        def fake_names(extra_paths=None) -> set[str]:
            return set(names)

        # Evidence runner side
        monkeypatch.setattr(
            "i2e_core.evidence_runner.load_provider", fake_load
        )
        monkeypatch.setattr(
            "i2e_core.evidence_runner.installed_provider_names", fake_names
        )
        # Orchestrator preflight side
        monkeypatch.setattr(
            "i2e_core.orchestrator.installed_provider_names", fake_names
        )

    return _install


__all__ = [
    "FakeProvider",
    "always_fail",
    "always_pass",
    "target_met",
]
