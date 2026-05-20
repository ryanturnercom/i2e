"""Fixtures for the evidence-runner tests.

We avoid running real pytest subprocesses (that's epic 02's domain) by
injecting a ``FakeProvider`` for each scenario via ``monkeypatch`` on
``i2e_core.evidence_runner.load_provider`` and
``i2e_core.evidence_runner.installed_provider_names``.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pytest

from i2e_core.evidence import ItemVerdict
from i2e_core.provider import (
    AsyncResult,
    CaseResult,
    ProviderContext,
    ProviderResult,
    TargetResult,
)


# ---------- Fake provider plumbing ----------


@dataclass
class FakeProvider:
    """A provider whose ``invoke`` returns a configurable result.

    ``behavior`` is a callable ``(item, ctx) -> ProviderResult`` so each test
    can model passing / failing / raising / async-flow scenarios without
    touching the filesystem.
    """

    name: str
    behavior: Callable[[object, ProviderContext], ProviderResult]

    def invoke(self, item, ctx: ProviderContext) -> ProviderResult:
        return self.behavior(item, ctx)


def always_pass() -> Callable[[object, ProviderContext], CaseResult]:
    return lambda item, ctx: CaseResult(verdict="pass", output="ok")


def always_fail(output: str = "boom") -> Callable[[object, ProviderContext], CaseResult]:
    return lambda item, ctx: CaseResult(verdict="fail", output=output)


def always_raise(exc: Exception) -> Callable[[object, ProviderContext], ProviderResult]:
    def _raise(item, ctx):
        raise exc

    return _raise


# ---------- Project layouts ----------


_MINIMAL_CAP_TEMPLATE = """---
capability: {name}
created: 2026-05-19
updated: 2026-05-19
version: {version}
status: active
watcher: '@me'
---

# {title}

{description}

## Evidence of success

{evidence}

## Constraints

{constraints}
"""


def _write_intent(
    root: Path,
    name: str,
    *,
    evidence: list[dict],
    constraints: list[dict] | None = None,
    version: int = 1,
    title: str = "Demo capability",
    description: str = "A capability used in evidence-runner tests.",
) -> Path:
    """Write a minimal valid intent file. ``evidence`` and ``constraints`` are
    lists of plain dicts (id/type/provider/query/expect/effort)."""
    intents_dir = root / ".i2e" / "intents"
    intents_dir.mkdir(parents=True, exist_ok=True)

    def _block(items: list[dict]) -> str:
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

    body = _MINIMAL_CAP_TEMPLATE.format(
        name=name,
        title=title,
        description=description,
        version=version,
        evidence=_block(evidence),
        constraints=_block(constraints or []),
    )
    path = intents_dir / f"{name}.md"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A minimal ``.i2e/`` skeleton at ``tmp_path``."""
    for sub in ("context", "intents", "evidence", "pending", "logs"):
        (tmp_path / ".i2e" / sub).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def write_intent(project: Path) -> Callable[..., Path]:
    """Factory fixture: ``write_intent(name, evidence=..., constraints=...)``."""
    def _factory(name: str, **kwargs) -> Path:
        return _write_intent(project, name, **kwargs)

    return _factory


@pytest.fixture
def patch_providers(monkeypatch: pytest.MonkeyPatch) -> Callable[[dict[str, FakeProvider]], None]:
    """Install fake providers visible to ``evidence_runner.load_provider``.

    Usage::

        patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    """
    def _install(providers: dict[str, FakeProvider]) -> None:
        names = set(providers.keys())

        def fake_load(name: str, extra_paths=None):
            if name not in providers:
                raise LookupError(f"no fake provider for {name!r}")
            return providers[name]

        def fake_names(extra_paths=None) -> set[str]:
            return set(names)

        monkeypatch.setattr(
            "i2e_core.evidence_runner.load_provider", fake_load
        )
        monkeypatch.setattr(
            "i2e_core.evidence_runner.installed_provider_names", fake_names
        )

    return _install


__all__ = [
    "FakeProvider",
    "always_fail",
    "always_pass",
    "always_raise",
]
