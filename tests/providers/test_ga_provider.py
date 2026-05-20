"""Tests for ``i2e-provider-ga`` — the Google client libs are mocked.

The provider lazy-imports ``google.oauth2.service_account`` and
``google.analytics.data_v1beta`` inside ``_run_query``. We inject fake
modules into ``sys.modules`` so the import succeeds without needing the
real packages installed.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from i2e_core.intent import EvidenceItem
from i2e_core.provider import ProviderContext, TargetResult
from i2e_core.provider.discovery import installed_provider_names, load_provider


def _item(
    expect: str = ">=1000",
    query: str | None = None,
    window: str = "7daysAgo",
) -> EvidenceItem:
    if query is None:
        query = json.dumps({"metric": "eventCount", "dimensions": ["eventName"]})
    return EvidenceItem(
        id="signup-events",
        type="target",
        provider="ga",
        query=query,
        expect=expect,
        window=window,
    )


def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GA_PROPERTY_ID", "12345")
    monkeypatch.setenv("GA_SERVICE_ACCOUNT_JSON_PATH", "/tmp/sa.json")


def _install_fake_google(metric_value: float | None = 1500.0) -> MagicMock:
    """Inject fake ``google.oauth2`` and ``google.analytics.data_v1beta`` modules.

    Returns the MagicMock standing in for the ``BetaAnalyticsDataClient`` class
    so callers can assert on ``run_report`` invocation.
    """
    # google.oauth2.service_account
    oauth2 = types.ModuleType("google.oauth2")
    sa_mod = types.ModuleType("google.oauth2.service_account")
    creds_cls = MagicMock(name="Credentials")
    creds_cls.from_service_account_file = MagicMock(return_value=MagicMock())
    sa_mod.Credentials = creds_cls

    # google.analytics.data_v1beta.{BetaAnalyticsDataClient, types}
    analytics = types.ModuleType("google.analytics")
    data_v1beta = types.ModuleType("google.analytics.data_v1beta")
    client_mock = MagicMock(name="BetaAnalyticsDataClientInstance")
    if metric_value is None:
        client_mock.run_report.return_value = MagicMock(rows=[])
    else:
        row = MagicMock()
        mv = MagicMock()
        mv.value = str(metric_value)
        row.metric_values = [mv]
        client_mock.run_report.return_value = MagicMock(rows=[row])

    client_cls = MagicMock(name="BetaAnalyticsDataClient", return_value=client_mock)
    data_v1beta.BetaAnalyticsDataClient = client_cls

    types_mod = types.ModuleType("google.analytics.data_v1beta.types")
    for cls_name in ("DateRange", "Dimension", "Metric", "RunReportRequest"):
        setattr(types_mod, cls_name, MagicMock(name=cls_name))
    data_v1beta.types = types_mod

    # Stub a parent google package so attribute lookups work.
    google = types.ModuleType("google")

    sys.modules["google"] = google
    sys.modules["google.oauth2"] = oauth2
    sys.modules["google.oauth2.service_account"] = sa_mod
    sys.modules["google.analytics"] = analytics
    sys.modules["google.analytics.data_v1beta"] = data_v1beta
    sys.modules["google.analytics.data_v1beta.types"] = types_mod
    return client_cls


def _uninstall_fake_google() -> None:
    for name in [
        "google.analytics.data_v1beta.types",
        "google.analytics.data_v1beta",
        "google.analytics",
        "google.oauth2.service_account",
        "google.oauth2",
        "google",
    ]:
        sys.modules.pop(name, None)


# ---------- discovery ----------


def test_discovery_finds_ga(fake_skills_root: Path) -> None:
    names = installed_provider_names(extra_paths=[fake_skills_root])
    assert "ga" in names


def test_load_ga_returns_named_provider(fake_skills_root: Path) -> None:
    provider = load_provider("ga", extra_paths=[fake_skills_root])
    assert provider.name == "ga"


# ---------- missing libs → actionable error ----------


def test_missing_optional_deps_raises_actionable(
    fake_skills_root: Path,
    provider_ctx: ProviderContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    # Make sure the fake google modules are NOT installed, so the lazy import
    # raises ImportError → provider should raise RuntimeError with install hint.
    _uninstall_fake_google()
    provider = load_provider("ga", extra_paths=[fake_skills_root])
    with pytest.raises(RuntimeError, match=r"pip install i2e_core\[ga\]"):
        provider.invoke(_item(), provider_ctx)


# ---------- env-var enforcement ----------


def test_missing_env_raises(
    fake_skills_root: Path,
    provider_ctx: ProviderContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GA_PROPERTY_ID", raising=False)
    monkeypatch.delenv("GA_SERVICE_ACCOUNT_JSON_PATH", raising=False)
    provider = load_provider("ga", extra_paths=[fake_skills_root])
    with pytest.raises(RuntimeError, match="GA_PROPERTY_ID"):
        provider.invoke(_item(), provider_ctx)


# ---------- happy path with mocked client ----------


def test_met_when_value_above_threshold(
    fake_skills_root: Path,
    provider_ctx: ProviderContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    try:
        client_cls = _install_fake_google(metric_value=1500.0)
        provider = load_provider("ga", extra_paths=[fake_skills_root])
        result = provider.invoke(_item(">=1000"), provider_ctx)
        assert isinstance(result, TargetResult)
        assert result.met == "met"
        assert result.value == "1500"
        assert client_cls.called
    finally:
        _uninstall_fake_google()


def test_unmet_when_value_below_threshold(
    fake_skills_root: Path,
    provider_ctx: ProviderContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    try:
        _install_fake_google(metric_value=200.0)
        provider = load_provider("ga", extra_paths=[fake_skills_root])
        result = provider.invoke(_item(">=1000"), provider_ctx)
        assert result.met == "unmet"
    finally:
        _uninstall_fake_google()


def test_no_rows_returns_zero(
    fake_skills_root: Path,
    provider_ctx: ProviderContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    try:
        _install_fake_google(metric_value=None)  # no rows
        provider = load_provider("ga", extra_paths=[fake_skills_root])
        result = provider.invoke(_item(">=1000"), provider_ctx)
        assert result.value == "0"
        assert result.met == "unmet"
    finally:
        _uninstall_fake_google()


# ---------- query parsing ----------


def test_invalid_json_query_raises(
    fake_skills_root: Path,
    provider_ctx: ProviderContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    try:
        _install_fake_google()
        provider = load_provider("ga", extra_paths=[fake_skills_root])
        item = _item(query="not json")
        with pytest.raises(ValueError, match="JSON"):
            provider.invoke(item, provider_ctx)
    finally:
        _uninstall_fake_google()


def test_query_missing_metric_raises(
    fake_skills_root: Path,
    provider_ctx: ProviderContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    try:
        _install_fake_google()
        provider = load_provider("ga", extra_paths=[fake_skills_root])
        item = _item(query=json.dumps({"dimensions": ["eventName"]}))
        with pytest.raises(ValueError, match="metric"):
            provider.invoke(item, provider_ctx)
    finally:
        _uninstall_fake_google()
