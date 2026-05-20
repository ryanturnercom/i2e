"""Unit tests for the provider contract result shapes + ``to_item_verdict``."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import pytest

from i2e_core.provider import (
    AsyncResult,
    CaseResult,
    Provider,
    ProviderContext,
    TargetResult,
    to_item_verdict,
)


def test_case_result_dataclass_round_trip() -> None:
    r = CaseResult(verdict="pass", output="ok")
    d = dataclasses.asdict(r)
    assert d == {"verdict": "pass", "output": "ok"}


def test_target_result_dataclass_round_trip() -> None:
    when = datetime(2026, 5, 19, tzinfo=timezone.utc)
    r = TargetResult(value="42", met="met", observed_at=when)
    d = dataclasses.asdict(r)
    assert d["value"] == "42"
    assert d["met"] == "met"
    assert d["observed_at"] == when


def test_async_result_dataclass_round_trip() -> None:
    r = AsyncResult(pending="2026-05-19-cap-item.yaml")
    assert r.verdict == "awaiting_human"
    d = dataclasses.asdict(r)
    assert d["pending"] == "2026-05-19-cap-item.yaml"
    assert d["verdict"] == "awaiting_human"


# ---------- to_item_verdict ----------


def test_to_item_verdict_pass_keeps_attempts() -> None:
    iv = to_item_verdict(CaseResult(verdict="pass", output="ok"), prev_attempts=3)
    assert iv.verdict == "pass"
    assert iv.attempts_used == 3
    assert iv.last_observed is not None


def test_to_item_verdict_fail_increments_attempts() -> None:
    iv = to_item_verdict(CaseResult(verdict="fail", output="boom"), prev_attempts=2)
    assert iv.verdict == "fail"
    assert iv.attempts_used == 3
    assert iv.raw == {"output": "boom"}


def test_to_item_verdict_target_met_keeps_attempts() -> None:
    when = datetime(2026, 5, 19, tzinfo=timezone.utc)
    iv = to_item_verdict(
        TargetResult(value="0.95", met="met", observed_at=when), prev_attempts=1
    )
    assert iv.verdict == "met"
    assert iv.value == "0.95"
    assert iv.attempts_used == 1
    assert iv.last_observed == when


def test_to_item_verdict_target_unmet_increments() -> None:
    when = datetime(2026, 5, 19, tzinfo=timezone.utc)
    iv = to_item_verdict(
        TargetResult(value="0.30", met="unmet", observed_at=when), prev_attempts=1
    )
    assert iv.verdict == "unmet"
    assert iv.attempts_used == 2


def test_to_item_verdict_target_trending_increments() -> None:
    when = datetime(2026, 5, 19, tzinfo=timezone.utc)
    iv = to_item_verdict(
        TargetResult(value="0.60", met="trending", observed_at=when), prev_attempts=4
    )
    assert iv.verdict == "trending"
    assert iv.attempts_used == 5


def test_to_item_verdict_async_keeps_attempts() -> None:
    iv = to_item_verdict(AsyncResult(pending="x.yaml"), prev_attempts=2)
    assert iv.verdict == "awaiting_human"
    assert iv.pending == "x.yaml"
    assert iv.attempts_used == 2


def test_to_item_verdict_unknown_type_raises() -> None:
    with pytest.raises(TypeError):
        to_item_verdict("not-a-result", prev_attempts=0)  # type: ignore[arg-type]


# ---------- Provider Protocol runtime check ----------


def test_provider_protocol_is_runtime_checkable() -> None:
    class Dummy:
        name = "dummy"

        def invoke(self, item, ctx):
            return CaseResult(verdict="pass")

    assert isinstance(Dummy(), Provider)


def test_provider_context_construction(tmp_path) -> None:
    from i2e_core.config import default_config

    ctx = ProviderContext(
        root=tmp_path,
        capability="cap",
        run_id="2026-05-19-abcdef",
        cfg=default_config(),
    )
    assert ctx.capability == "cap"
    assert ctx.run_id == "2026-05-19-abcdef"
