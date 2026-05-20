"""i2e-provider-survey — async survey provider with numeric verdict options.

Writes a ``kind: human_evaluation`` pending file with the numeric scale as
``verdict_options``. The resolver (``i2e_core.pending.resolve_to_verdict``)
translates a numeric resolution into a ``TargetResult``-equivalent verdict
using the item's ``expect`` (a comparison expression like ``">=8"``).

The scale is selected via ``item.query`` — a JSON object::

    {"prompt": "How likely to recommend?", "scale": "nps", "followup": "Why?"}

Supported scales:

- ``nps``    — 0-10 (default)
- ``likert`` — 1-5
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from i2e_core.pending import PendingFile, write_pending
from i2e_core.provider import AsyncResult, ProviderContext


_SCALE_OPTIONS: dict[str, list[str]] = {
    "nps": [str(n) for n in range(0, 11)],
    "likert": [str(n) for n in range(1, 6)],
}


def _parse_spec(query: str) -> dict:
    """Parse the JSON survey spec, with sensible defaults."""
    if not query:
        raise ValueError("i2e-provider-survey: query must be a JSON object")
    try:
        data = json.loads(query)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"i2e-provider-survey: query must be JSON ({e.msg})"
        ) from e
    if not isinstance(data, dict):
        raise ValueError(
            "i2e-provider-survey: query JSON must be an object with at least a `prompt`"
        )
    return data


def _format_ask(spec: dict, scale_key: str) -> str:
    prompt = spec.get("prompt") or "(no prompt provided)"
    followup = spec.get("followup")
    scale_label = {
        "nps": "Rate 0-10 (Net Promoter scale)",
        "likert": "Rate 1-5 (Likert agreement scale)",
    }.get(scale_key, f"Rate on the {scale_key} scale")
    lines = [prompt, "", scale_label]
    if followup:
        lines.extend(["", f"Follow-up: {followup}"])
    return "\n".join(lines)


class SurveyProvider:
    name = "survey"

    def invoke(self, item, ctx: ProviderContext) -> AsyncResult:
        spec = _parse_spec(getattr(item, "query", ""))
        scale_key = (spec.get("scale") or "nps").strip().lower()
        if scale_key not in _SCALE_OPTIONS:
            raise ValueError(
                f"i2e-provider-survey: unknown scale {scale_key!r} "
                f"(supported: {sorted(_SCALE_OPTIONS)})"
            )
        verdict_options = list(_SCALE_OPTIONS[scale_key])

        now = datetime.now(timezone.utc)
        pf = PendingFile(
            kind="human_evaluation",
            capability=ctx.capability,
            item_id=item.id,
            asked_at=now,
            ask=_format_ask(spec, scale_key),
            expect=getattr(item, "expect", None),
            verdict_options=verdict_options,
        )
        path = write_pending(ctx.root, pf)
        return AsyncResult(pending=path.name)


provider = SurveyProvider()
