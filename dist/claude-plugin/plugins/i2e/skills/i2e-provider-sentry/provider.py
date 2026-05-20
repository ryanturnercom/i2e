"""i2e-provider-sentry — count Sentry events matching a query.

Shapes the result based on the ``expect`` field:

- ``expect: 0`` — constraint shape; ``pass`` iff the count is zero, else ``fail``
- any comparison expression (``<N``, ``<=N`` etc.) — target shape with
  ``value = "<count>"`` and ``met`` determined by the comparison

Configuration (env vars):

- ``SENTRY_AUTH_TOKEN``   — API token with ``event:read``
- ``SENTRY_ORG_SLUG``     — organization slug
- ``SENTRY_PROJECT_SLUG`` — project slug
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from i2e_core.provider import CaseResult, ProviderContext, TargetResult
from i2e_core.provider.expect_parser import compare, is_trending, parse_expect


def _require_env() -> tuple[str, str, str]:
    token = os.environ.get("SENTRY_AUTH_TOKEN")
    org = os.environ.get("SENTRY_ORG_SLUG")
    project = os.environ.get("SENTRY_PROJECT_SLUG")
    missing = [
        name
        for name, val in (
            ("SENTRY_AUTH_TOKEN", token),
            ("SENTRY_ORG_SLUG", org),
            ("SENTRY_PROJECT_SLUG", project),
        )
        if not val
    ]
    if missing:
        raise RuntimeError(
            "i2e-provider-sentry requires "
            + ", ".join(missing)
            + " in the environment"
        )
    return token, org, project  # type: ignore[return-value]


def _count_events(*, query: str, window: str) -> int:
    """Hit the Sentry events endpoint and count matches.

    For simplicity we use a single page and treat the returned array length
    as the count. A real-world deployment would consume the ``Link`` header
    pagination — out of scope for this provider's smoke needs.
    """
    token, org, project = _require_env()
    qs = urllib.parse.urlencode({"query": query, "statsPeriod": window})
    url = (
        f"https://sentry.io/api/0/projects/{org}/{project}/events/?{qs}"
    )
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # nosec - documented
            body = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise RuntimeError(
                f"Sentry API {e.code}: check SENTRY_AUTH_TOKEN scopes / org/project slugs"
            ) from e
        detail = e.read().decode("utf-8", "replace") if e.fp else ""
        raise RuntimeError(
            f"Sentry API error {e.code}: {detail[:200]}"
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Sentry API request failed: {e.reason}") from e

    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Sentry API returned non-JSON: {body[:200]!r}"
        ) from e
    if isinstance(data, dict) and "data" in data:
        data = data["data"]
    if not isinstance(data, list):
        raise RuntimeError(
            f"Sentry API returned unexpected payload shape: {type(data).__name__}"
        )
    return len(data)


class SentryProvider:
    name = "sentry"

    def invoke(
        self, item, ctx: ProviderContext
    ) -> CaseResult | TargetResult:
        expect = (getattr(item, "expect", "") or "").strip()
        window = getattr(item, "window", None) or "24h"
        count = _count_events(query=item.query, window=window)

        # Constraint shape: expect == "0" (bare zero — "must never happen")
        if expect == "0":
            if count == 0:
                return CaseResult(verdict="pass", output="0 matching events")
            return CaseResult(
                verdict="fail",
                output=f"{count} matching events (expected 0)",
            )

        # Target shape: any other expect is a comparison expression
        op, threshold, _unit = parse_expect(expect)
        value = float(count)
        if compare(value, op, threshold):
            met = "met"
        elif is_trending(value, op, threshold):
            met = "trending"
        else:
            met = "unmet"
        return TargetResult(
            value=str(count),
            met=met,
            observed_at=datetime.now(timezone.utc),
        )


provider = SentryProvider()
