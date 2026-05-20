"""Provider framework — contract, discovery, and result conversion.

The installed skill set *is* the provider registry. See ``discovery`` for the
mechanism that walks ``~/.claude/skills/`` and ``<project>/.claude/skills/``
looking for ``i2e-provider-*`` folders.
"""

from __future__ import annotations

from .contract import (
    AsyncResult,
    CaseResult,
    Provider,
    ProviderContext,
    ProviderResult,
    TargetResult,
    to_item_verdict,
)

__all__ = [
    "AsyncResult",
    "CaseResult",
    "Provider",
    "ProviderContext",
    "ProviderResult",
    "TargetResult",
    "to_item_verdict",
]
