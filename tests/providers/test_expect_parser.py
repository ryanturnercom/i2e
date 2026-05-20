"""Unit tests for the shared ``expect_parser`` module."""

from __future__ import annotations

import pytest

from i2e_core.provider.expect_parser import compare, is_trending, parse_expect


def test_parse_lt_with_unit() -> None:
    assert parse_expect("<50ms") == ("<", 50.0, "ms")


def test_parse_gte_percent() -> None:
    assert parse_expect(">=99%") == (">=", 99.0, "%")


def test_parse_eq_no_unit() -> None:
    assert parse_expect("==0") == ("==", 0.0, "")


def test_parse_with_spaces_and_decimals() -> None:
    assert parse_expect(" > 1.5s ") == (">", 1.5, "s")


def test_parse_le_no_unit() -> None:
    assert parse_expect("<= 250") == ("<=", 250.0, "")


def test_parse_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        parse_expect("not a comparison")


def test_parse_rejects_empty() -> None:
    with pytest.raises(ValueError):
        parse_expect("")


def test_parse_rejects_non_string() -> None:
    with pytest.raises(ValueError):
        parse_expect(42)  # type: ignore[arg-type]


def test_compare_lt_true() -> None:
    assert compare(40, "<", 50) is True


def test_compare_lt_false() -> None:
    assert compare(60, "<", 50) is False


def test_compare_gte_boundary() -> None:
    assert compare(99, ">=", 99) is True


def test_compare_eq_and_ne() -> None:
    assert compare(0, "==", 0) is True
    assert compare(1, "!=", 0) is True


def test_compare_rejects_unknown_op() -> None:
    with pytest.raises(ValueError):
        compare(1, "??", 1)


def test_is_trending_under_threshold_close() -> None:
    # threshold 50, observed 53 → within 10% of 50 (5) → trending
    assert is_trending(53, "<", 50) is True


def test_is_trending_under_threshold_far() -> None:
    assert is_trending(80, "<", 50) is False


def test_is_trending_not_when_met() -> None:
    assert is_trending(40, "<", 50) is False


def test_is_trending_above_threshold_close() -> None:
    # want >=99, observed 91 → within 10% of 99 (~9.9) → trending
    assert is_trending(91, ">=", 99) is True


def test_is_trending_eq_within_margin() -> None:
    # threshold 100, observed 105 → within 10% (slack=10) → trending
    assert is_trending(105, "==", 100) is True


def test_is_trending_eq_outside_margin() -> None:
    # threshold 100, observed 200 → well outside 10% slack
    assert is_trending(200, "==", 100) is False
