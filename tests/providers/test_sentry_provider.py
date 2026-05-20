"""Tests for ``i2e-provider-sentry`` — HTTP calls mocked at urlopen."""

from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from i2e_core.intent import Constraint, EvidenceItem
from i2e_core.provider import CaseResult, ProviderContext, TargetResult
from i2e_core.provider.discovery import installed_provider_names, load_provider


class _FakeResp:
    def __init__(self, body: Any):
        self._body = json.dumps(body).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *exc) -> None:
        return None


def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTRY_AUTH_TOKEN", "test-token")
    monkeypatch.setenv("SENTRY_ORG_SLUG", "my-org")
    monkeypatch.setenv("SENTRY_PROJECT_SLUG", "my-project")


def _constraint(expect: str = "0") -> Constraint:
    return Constraint(
        id="pii-not-logged",
        provider="sentry",
        query='events:contains("http") in:logs',
        expect=expect,
    )


def _target_item(expect: str = "<100") -> EvidenceItem:
    return EvidenceItem(
        id="error-rate",
        type="target",
        provider="sentry",
        query="error",
        expect=expect,
        window="1h",
    )


# ---------- discovery ----------


def test_discovery_finds_sentry(fake_skills_root: Path) -> None:
    names = installed_provider_names(extra_paths=[fake_skills_root])
    assert "sentry" in names


def test_load_sentry_returns_named_provider(fake_skills_root: Path) -> None:
    provider = load_provider("sentry", extra_paths=[fake_skills_root])
    assert provider.name == "sentry"


# ---------- env-var enforcement ----------


def test_missing_env_raises(
    fake_skills_root: Path,
    provider_ctx: ProviderContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for var in ("SENTRY_AUTH_TOKEN", "SENTRY_ORG_SLUG", "SENTRY_PROJECT_SLUG"):
        monkeypatch.delenv(var, raising=False)
    provider = load_provider("sentry", extra_paths=[fake_skills_root])
    with pytest.raises(RuntimeError, match="SENTRY_AUTH_TOKEN"):
        provider.invoke(_constraint(), provider_ctx)


# ---------- expect: 0 → CaseResult ----------


def test_expect_zero_pass_when_no_events(
    fake_skills_root: Path,
    provider_ctx: ProviderContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    provider = load_provider("sentry", extra_paths=[fake_skills_root])
    with patch("urllib.request.urlopen", return_value=_FakeResp([])):
        result = provider.invoke(_constraint("0"), provider_ctx)
    assert isinstance(result, CaseResult)
    assert result.verdict == "pass"


def test_expect_zero_fail_when_events_present(
    fake_skills_root: Path,
    provider_ctx: ProviderContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    provider = load_provider("sentry", extra_paths=[fake_skills_root])
    with patch(
        "urllib.request.urlopen",
        return_value=_FakeResp([{"id": "a"}, {"id": "b"}]),
    ):
        result = provider.invoke(_constraint("0"), provider_ctx)
    assert isinstance(result, CaseResult)
    assert result.verdict == "fail"
    assert "2" in result.output


# ---------- expect: <N → TargetResult ----------


def test_expect_lt_met(
    fake_skills_root: Path,
    provider_ctx: ProviderContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    provider = load_provider("sentry", extra_paths=[fake_skills_root])
    # 3 events, expect <100 → met
    with patch(
        "urllib.request.urlopen",
        return_value=_FakeResp([{}] * 3),
    ):
        result = provider.invoke(_target_item("<100"), provider_ctx)
    assert isinstance(result, TargetResult)
    assert result.met == "met"
    assert result.value == "3"


def test_expect_lt_unmet(
    fake_skills_root: Path,
    provider_ctx: ProviderContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    provider = load_provider("sentry", extra_paths=[fake_skills_root])
    with patch(
        "urllib.request.urlopen",
        return_value=_FakeResp([{}] * 150),
    ):
        result = provider.invoke(_target_item("<100"), provider_ctx)
    assert isinstance(result, TargetResult)
    assert result.met == "unmet"


def test_payload_with_data_wrapper(
    fake_skills_root: Path,
    provider_ctx: ProviderContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Some Sentry endpoints return ``{"data": [...]}`` — provider unwraps."""
    _env(monkeypatch)
    provider = load_provider("sentry", extra_paths=[fake_skills_root])
    with patch(
        "urllib.request.urlopen",
        return_value=_FakeResp({"data": [{"id": "a"}]}),
    ):
        result = provider.invoke(_target_item("<100"), provider_ctx)
    assert result.value == "1"


# ---------- HTTP 401 / 403 ----------


def test_http_401_actionable_message(
    fake_skills_root: Path,
    provider_ctx: ProviderContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    provider = load_provider("sentry", extra_paths=[fake_skills_root])
    err = urllib.error.HTTPError(
        url="https://sentry.io/api/0/projects/my-org/my-project/events/",
        code=401,
        msg="Unauthorized",
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(b'{"detail":"Invalid token"}'),
    )
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(RuntimeError, match="SENTRY_AUTH_TOKEN"):
            provider.invoke(_constraint("0"), provider_ctx)


def test_http_500_surfaces_body(
    fake_skills_root: Path,
    provider_ctx: ProviderContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch)
    provider = load_provider("sentry", extra_paths=[fake_skills_root])
    err = urllib.error.HTTPError(
        url="https://sentry.io/api/0/projects/my-org/my-project/events/",
        code=500,
        msg="Server Error",
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(b"boom"),
    )
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(RuntimeError, match="500"):
            provider.invoke(_constraint("0"), provider_ctx)
