"""Provider contract: result shapes, ProviderContext, and the Provider Protocol.

Spec §4.2 defines three verdict shapes:

- Case      → `{ verdict: pass | fail, output: "..." }`
- Target    → `{ value: <observed>, met: met | unmet | trending, observed_at }`
- Constraint → same shape as Case
- Async     → `{ verdict: awaiting_human, pending: <basename> }`

These are intentionally light-weight ``@dataclass`` instances (not Pydantic models)
because providers instantiate them inline. The Pydantic boundary is at
``ItemVerdict``, which is what we persist into ``current.yaml``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol, Union, runtime_checkable

from ..config import I2EConfig
from ..evidence import ItemVerdict

if TYPE_CHECKING:  # pragma: no cover - import for type checkers only
    from ..intent import Constraint, EvidenceItem


# ---------- Result dataclasses ----------


@dataclass
class CaseResult:
    """Result for a Case or Constraint provider invocation."""

    verdict: Literal["pass", "fail"]
    output: str = ""


@dataclass
class TargetResult:
    """Result for a Target provider invocation."""

    value: str
    met: Literal["met", "unmet", "trending"]
    observed_at: datetime


@dataclass
class AsyncResult:
    """Result for an asynchronous provider invocation (pending file written)."""

    pending: str
    verdict: Literal["awaiting_human"] = "awaiting_human"


ProviderResult = Union[CaseResult, TargetResult, AsyncResult]


# ---------- Provider context ----------


@dataclass
class ProviderContext:
    """Runtime context passed to every provider invocation."""

    root: Path
    capability: str
    run_id: str
    cfg: I2EConfig


# ---------- Provider protocol ----------


@runtime_checkable
class Provider(Protocol):
    """Duck-typed contract a provider helper module's ``provider`` instance must satisfy."""

    name: str

    def invoke(
        self,
        item: "EvidenceItem | Constraint",
        ctx: ProviderContext,
    ) -> ProviderResult:  # pragma: no cover - protocol body
        ...


# ---------- Converters ----------


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_item_verdict(
    result: ProviderResult,
    *,
    prev_attempts: int = 0,
) -> ItemVerdict:
    """Convert a provider result into the persisted ``ItemVerdict`` shape.

    ``attempts_used`` is incremented for ``fail``/``unmet``/``trending`` and left
    at ``prev_attempts`` for ``pass``/``met``/``awaiting_human``.
    """

    if isinstance(result, CaseResult):
        if result.verdict == "pass":
            return ItemVerdict(
                verdict="pass",
                attempts_used=prev_attempts,
                last_observed=_now_utc(),
            )
        return ItemVerdict(
            verdict="fail",
            attempts_used=prev_attempts + 1,
            last_observed=_now_utc(),
            raw={"output": result.output},
        )

    if isinstance(result, TargetResult):
        if result.met == "met":
            return ItemVerdict(
                verdict="met",
                value=result.value,
                attempts_used=prev_attempts,
                last_observed=result.observed_at,
            )
        return ItemVerdict(
            verdict=result.met,  # "unmet" or "trending"
            value=result.value,
            attempts_used=prev_attempts + 1,
            last_observed=result.observed_at,
        )

    if isinstance(result, AsyncResult):
        return ItemVerdict(
            verdict="awaiting_human",
            attempts_used=prev_attempts,
            pending=result.pending,
        )

    raise TypeError(f"Unknown provider result type: {type(result).__name__}")


__all__ = [
    "AsyncResult",
    "CaseResult",
    "Provider",
    "ProviderContext",
    "ProviderResult",
    "TargetResult",
    "to_item_verdict",
]
