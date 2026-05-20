"""i2e-provider-ga — Google Analytics 4 Data API provider.

Lazy-imports the Google client libraries inside ``_run_query`` so the provider
file can be discovered (skill manifest scan, etc.) even when the optional
``ga`` extra is not installed. Calling ``invoke`` without those libraries
raises a clear ``RuntimeError`` pointing the operator at::

    pip install i2e_core[ga]

Tests mock the lazy-imported client at the module level via
``unittest.mock.patch.dict`` on ``sys.modules`` so no real Google
credentials or network calls are exercised.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from i2e_core.provider import ProviderContext, TargetResult
from i2e_core.provider.expect_parser import compare, is_trending, parse_expect


def _require_env() -> tuple[str, str]:
    property_id = os.environ.get("GA_PROPERTY_ID")
    sa_path = os.environ.get("GA_SERVICE_ACCOUNT_JSON_PATH")
    missing = [
        name
        for name, val in (
            ("GA_PROPERTY_ID", property_id),
            ("GA_SERVICE_ACCOUNT_JSON_PATH", sa_path),
        )
        if not val
    ]
    if missing:
        raise RuntimeError(
            "i2e-provider-ga requires "
            + ", ".join(missing)
            + " in the environment"
        )
    return property_id, sa_path  # type: ignore[return-value]


def _parse_query(query: str) -> dict[str, Any]:
    """Parse the JSON query payload into a dict."""
    if not query:
        raise ValueError("i2e-provider-ga: query must be a non-empty JSON object")
    try:
        data = json.loads(query)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"i2e-provider-ga: query must be JSON ({e.msg})"
        ) from e
    if not isinstance(data, dict):
        raise ValueError(
            "i2e-provider-ga: query JSON must be an object with `metric` and optional `dimensions`"
        )
    if "metric" not in data:
        raise ValueError(
            "i2e-provider-ga: query JSON is missing required `metric`"
        )
    return data


def _run_query(
    *,
    property_id: str,
    sa_path: str,
    metric: str,
    dimensions: list[str],
    start_date: str,
    end_date: str,
) -> float:
    """Call the GA4 Data API and return the scalar metric value.

    Lazy-imports the Google libraries; raises ``RuntimeError`` with an actionable
    message if the optional dependencies are not installed.
    """
    try:
        from google.oauth2 import service_account  # type: ignore
        from google.analytics.data_v1beta import BetaAnalyticsDataClient  # type: ignore
        from google.analytics.data_v1beta.types import (  # type: ignore
            DateRange,
            Dimension,
            Metric,
            RunReportRequest,
        )
    except ImportError as e:
        raise RuntimeError(
            "i2e-provider-ga requires the optional GA extras. "
            "Install them with: pip install i2e_core[ga]"
        ) from e

    credentials = service_account.Credentials.from_service_account_file(sa_path)
    client = BetaAnalyticsDataClient(credentials=credentials)
    req = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimensions=[Dimension(name=d) for d in dimensions],
        metrics=[Metric(name=metric)],
    )
    resp = client.run_report(req)

    # Sum all rows for the requested metric. For a single-metric, single-dim
    # query that's the full event count; for dimensionless queries the response
    # is a single row.
    rows = list(getattr(resp, "rows", []) or [])
    if not rows:
        return 0.0
    total = 0.0
    for row in rows:
        for mv in getattr(row, "metric_values", []) or []:
            raw = getattr(mv, "value", None)
            if raw is None:
                continue
            try:
                total += float(raw)
            except (TypeError, ValueError):
                continue
    return total


class GaProvider:
    name = "ga"

    def invoke(self, item, ctx: ProviderContext) -> TargetResult:
        property_id, sa_path = _require_env()
        op, threshold, unit = parse_expect(getattr(item, "expect", ""))
        spec = _parse_query(getattr(item, "query", ""))
        metric = spec["metric"]
        dimensions = list(spec.get("dimensions") or [])
        window = getattr(item, "window", None) or "7daysAgo"
        # Window is interpreted as the GA `startDate`; end is always "today".
        start_date = window if "Ago" in window or window == "today" else window

        value = _run_query(
            property_id=property_id,
            sa_path=sa_path,
            metric=metric,
            dimensions=dimensions,
            start_date=start_date,
            end_date="today",
        )

        if compare(value, op, threshold):
            met = "met"
        elif is_trending(value, op, threshold):
            met = "trending"
        else:
            met = "unmet"

        value_str = (
            f"{int(value)}{unit}" if value.is_integer() else f"{value}{unit}"
        )
        return TargetResult(
            value=value_str, met=met, observed_at=datetime.now(timezone.utc)
        )


provider = GaProvider()
