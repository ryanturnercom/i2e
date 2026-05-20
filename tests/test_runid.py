"""Tests for `i2e_core.runid`."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone

import pytest

from i2e_core import runid


def test_new_run_id_format():
    rid = runid.new_run_id()
    assert re.match(r"^\d{4}-\d{2}-\d{2}-[0-9a-f]{6}$", rid)


def test_new_run_id_unique():
    a = runid.new_run_id()
    b = runid.new_run_id()
    assert a != b


def test_new_run_id_honours_now():
    ts = datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    rid = runid.new_run_id(ts)
    assert rid.startswith("2025-01-02-")


def test_parse_run_id_ok():
    d, suffix = runid.parse_run_id("2026-05-19-abcd12")
    assert d == date(2026, 5, 19)
    assert suffix == "abcd12"


def test_parse_run_id_bad():
    with pytest.raises(ValueError):
        runid.parse_run_id("not-a-run-id")
