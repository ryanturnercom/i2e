"""i2e-provider-human — async provider that writes a pending file.

Returns ``awaiting_human`` on first ask. The orchestrator picks up the
resolution from ``.i2e/pending/`` on a later tick.
"""

from __future__ import annotations

from datetime import datetime, timezone

from i2e_core.pending import PendingFile, write_pending
from i2e_core.provider import AsyncResult, ProviderContext


class HumanProvider:
    name = "human"

    def invoke(self, item, ctx: ProviderContext) -> AsyncResult:
        now = datetime.now(timezone.utc)
        pf = PendingFile(
            kind="human_evaluation",
            capability=ctx.capability,
            item_id=item.id,
            asked_at=now,
            ask=item.query,
            expect=getattr(item, "expect", None),
            verdict_options=["yes", "no", "partial"],
            url=getattr(item, "url", None),
            steps=getattr(item, "steps", None),
            screenshot=getattr(item, "screenshot", None),
        )
        path = write_pending(ctx.root, pf)
        return AsyncResult(pending=path.name)


provider = HumanProvider()
