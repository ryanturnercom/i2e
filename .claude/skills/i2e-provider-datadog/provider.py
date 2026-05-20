"""i2e-provider-datadog — queries a Datadog metric over a window.

Returns a Target verdict comparing the latest non-null point against the
item's ``expect`` expression.

Configuration (env vars):

- ``DATADOG_API_KEY`` — API key (required)
- ``DATADOG_APP_KEY`` — Application key (required)
- ``DATADOG_SITE``    — site domain, default ``datadoghq.com``

The HTTP call uses ``urllib.request`` so the provider stays stdlib-only.
Tests mock ``urllib.request.urlopen`` to keep the suite hermetic.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from i2e_core.provider import ProviderContext, TargetResult
from i2e_core.provider.expect_parser import compare, is_trending, parse_expect


_WINDOW_UNIT_SECS = {"m": 60, "h": 3600, "d": 86400, "w": 604800}


def _parse_window_seconds(s: str) -> int:
    """Parse a window like ``"5m"`` into a seconds count.

    Raises ``ValueError`` for unsupported shapes.
    """
    s = (s or "").strip()
    if not s or s[-1] not in _WINDOW_UNIT_SECS or not s[:-1].isdigit():
        raise ValueError(
            f"window {s!r} not understood (use e.g. '5m', '2h', '7d')"
        )
    return int(s[:-1]) * _WINDOW_UNIT_SECS[s[-1]]


def _require_env() -> tuple[str, str, str]:
    api_key = os.environ.get("DATADOG_API_KEY")
    app_key = os.environ.get("DATADOG_APP_KEY")
    site = os.environ.get("DATADOG_SITE", "datadoghq.com")
    missing = [
        name
        for name, val in (
            ("DATADOG_API_KEY", api_key),
            ("DATADOG_APP_KEY", app_key),
        )
        if not val
    ]
    if missing:
        raise RuntimeError(
            "i2e-provider-datadog requires "
            + ", ".join(missing)
            + " in the environment"
        )
    return api_key, app_key, site  # type: ignore[return-value]


def _query_datadog(
    *, query: str, from_ts: int, to_ts: int
) -> dict[str, Any]:
    """Call ``GET /api/v1/query`` and return the parsed JSON body.

    Raises ``RuntimeError`` for HTTP 4xx/5xx, decorated with the response body
    so the operator can see the upstream error message.
    """
    api_key, app_key, site = _require_env()
    base = f"https://api.{site}"
    qs = urllib.parse.urlencode(
        {"from": from_ts, "to": to_ts, "query": query}
    )
    url = f"{base}/api/v1/query?{qs}"
    req = urllib.request.Request(
        url,
        headers={
            "DD-API-KEY": api_key,
            "DD-APPLICATION-KEY": app_key,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # nosec - documented use
            body = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace") if e.fp else ""
        raise RuntimeError(
            f"Datadog API error {e.code} on /api/v1/query: {detail[:200]}"
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Datadog API request failed: {e.reason}") from e
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Datadog API returned non-JSON: {body[:200]!r}"
        ) from e


def _latest_value(payload: dict[str, Any]) -> float:
    """Pull the most recent non-null point from a Datadog query response."""
    series = payload.get("series") or []
    if not series:
        raise RuntimeError("Datadog response contained no series")
    first = series[0]
    pointlist = first.get("pointlist") or []
    # pointlist is a list of [ts_ms, value]; iterate newest-last and find the
    # latest non-null sample.
    for ts, val in reversed(pointlist):
        if val is not None:
            return float(val)
    raise RuntimeError("Datadog series contained only null points")


class DatadogProvider:
    name = "datadog"

    def invoke(self, item, ctx: ProviderContext) -> TargetResult:
        op, threshold, unit = parse_expect(getattr(item, "expect", ""))
        window = getattr(item, "window", None) or "5m"
        secs = _parse_window_seconds(window)
        now = datetime.now(timezone.utc)
        to_ts = int(now.timestamp())
        from_ts = to_ts - secs

        payload = _query_datadog(
            query=item.query, from_ts=from_ts, to_ts=to_ts
        )
        value = _latest_value(payload)

        if compare(value, op, threshold):
            met = "met"
        elif is_trending(value, op, threshold):
            met = "trending"
        else:
            met = "unmet"

        # Render the value with the unit from the expect expression (no unit
        # interpolation — we trust the operator to keep them consistent).
        if value.is_integer():
            value_str = f"{int(value)}{unit}"
        else:
            value_str = f"{value}{unit}"

        return TargetResult(value=value_str, met=met, observed_at=now)


provider = DatadogProvider()
