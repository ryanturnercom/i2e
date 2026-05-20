"""Tests for ``i2e-provider-datadog`` — HTTP calls are mocked.

The provider is loaded via the real ``discovery`` path (same as production),
so we exercise the full skill-installation contract end-to-end. The Datadog
HTTP layer is mocked at ``urllib.request.urlopen`` so no real requests fire.
"""

from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from i2e_core.intent import EvidenceItem
from i2e_core.provider import ProviderContext, TargetResult
from i2e_core.provider.discovery import installed_provider_names, load_provider


def _item(expect: str = "<50ms", window: str | None = "5m") -> EvidenceItem:
    return EvidenceItem(
        id="redirect-latency-p95",
        type="target",
        provider="datadog",
        query="redirect_latency{quantile=0.95}",
        expect=expect,
        window=window,
    )


class _FakeResp:
    """Minimal stand-in for ``http.client.HTTPResponse`` used by urlopen."""

    def __init__(self, body: dict[str, Any]):
        self._body = json.dumps(body).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *exc) -> None:
        return None


def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATADOG_API_KEY", "test-api-key")
    monkeypatch.setenv("DATADOG_APP_KEY", "test-app-key")


# ---------- discovery + skill manifest ----------


def test_discovery_finds_datadog(fake_skills_root: Path) -> None:
    names = installed_provider_names(extra_paths=[fake_skills_root])
    assert "datadog" in names


def test_load_datadog_returns_named_provider(fake_skills_root: Path) -> None:
    provider = load_provider("datadog", extra_paths=[fake_skills_root])
    assert provider.name == "datadog"


# ---------- env-var enforcement ----------


def test_missing_env_raises_runtime_error(
    fake_skills_root: Path,
    provider_ctx: ProviderContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATADOG_API_KEY", raising=False)
    monkeypatch.delenv("DATADOG_APP_KEY", raising=False)
    provider = load_provider("datadog", extra_paths=[fake_skills_root])
    with pytest.raises(RuntimeError, match="DATADOG_API_KEY"):
        provider.invoke(_item(), provider_ctx)


# ---------- happy paths ----------


def test_met_when_value_under_threshold(
    fake_skills_root: Path,
    provider_ctx: ProviderContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    provider = load_provider("datadog", extra_paths=[fake_skills_root])
    payload = {"series": [{"pointlist": [[1000, 30.0], [2000, 42.0]]}]}
    with patch(
        "urllib.request.urlopen", return_value=_FakeResp(payload)
    ) as mock_open:
        result = provider.invoke(_item("<50ms"), provider_ctx)
    assert mock_open.called
    assert isinstance(result, TargetResult)
    assert result.met == "met"
    assert result.value == "42ms"


def test_unmet_when_value_above_threshold(
    fake_skills_root: Path,
    provider_ctx: ProviderContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    provider = load_provider("datadog", extra_paths=[fake_skills_root])
    payload = {"series": [{"pointlist": [[1000, 80.0]]}]}
    with patch("urllib.request.urlopen", return_value=_FakeResp(payload)):
        result = provider.invoke(_item("<50ms"), provider_ctx)
    assert result.met == "unmet"
    assert result.value == "80ms"


def test_trending_within_margin(
    fake_skills_root: Path,
    provider_ctx: ProviderContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    provider = load_provider("datadog", extra_paths=[fake_skills_root])
    # threshold 50, observed 53 → within 10% of 50 → trending
    payload = {"series": [{"pointlist": [[1000, 53.0]]}]}
    with patch("urllib.request.urlopen", return_value=_FakeResp(payload)):
        result = provider.invoke(_item("<50ms"), provider_ctx)
    assert result.met == "trending"


def test_uses_latest_non_null_point(
    fake_skills_root: Path,
    provider_ctx: ProviderContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    provider = load_provider("datadog", extra_paths=[fake_skills_root])
    payload = {
        "series": [
            {"pointlist": [[1000, 10.0], [2000, 15.0], [3000, None]]}
        ]
    }
    with patch("urllib.request.urlopen", return_value=_FakeResp(payload)):
        result = provider.invoke(_item("<50ms"), provider_ctx)
    # Latest non-null is 15
    assert result.value == "15ms"


# ---------- error paths ----------


def test_http_error_raises_runtime(
    fake_skills_root: Path,
    provider_ctx: ProviderContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    provider = load_provider("datadog", extra_paths=[fake_skills_root])
    err = urllib.error.HTTPError(
        url="https://api.datadoghq.com/api/v1/query",
        code=401,
        msg="Unauthorized",
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(b'{"errors":["invalid API key"]}'),
    )
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(RuntimeError, match="401"):
            provider.invoke(_item(), provider_ctx)


def test_empty_series_raises(
    fake_skills_root: Path,
    provider_ctx: ProviderContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    provider = load_provider("datadog", extra_paths=[fake_skills_root])
    with patch(
        "urllib.request.urlopen", return_value=_FakeResp({"series": []})
    ):
        with pytest.raises(RuntimeError, match="no series"):
            provider.invoke(_item(), provider_ctx)


def test_unparseable_window_raises(
    fake_skills_root: Path,
    provider_ctx: ProviderContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    provider = load_provider("datadog", extra_paths=[fake_skills_root])
    with pytest.raises(ValueError, match="window"):
        provider.invoke(_item(window="30s"), provider_ctx)
