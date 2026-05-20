"""Shared parser for ``expect`` comparison expressions used by Target providers.

Examples accepted::

    <50ms     -> ("<",  50.0, "ms")
    >=99%     -> (">=", 99.0, "%")
    ==0       -> ("==",  0.0, "")
    > 1.5s    -> (">",   1.5, "s")
    <= 250    -> ("<=",250.0, "")

The unit is whatever non-whitespace follows the number; the caller decides
how to compare observed values against the threshold (Target providers
typically observe a raw number and just compare numerically, dropping the
unit). Negative numbers are not currently supported — none of the spec's
example metrics need them.
"""

from __future__ import annotations

import re

_EXPECT_RE = re.compile(
    r"""
    ^\s*
    (?P<op>==|!=|<=|>=|<|>)
    \s*
    (?P<num>\d+(?:\.\d+)?)
    \s*
    (?P<unit>[^\s]*)
    \s*$
    """,
    re.VERBOSE,
)


def parse_expect(s: str) -> tuple[str, float, str]:
    """Parse a comparison expression like ``"<50ms"`` into ``(op, threshold, unit)``.

    Raises ``ValueError`` on any other shape (empty string, bare number, etc.).
    """
    if not isinstance(s, str):
        raise ValueError(f"expect must be a string, got {type(s).__name__}")
    m = _EXPECT_RE.match(s)
    if not m:
        raise ValueError(
            f"could not parse expect {s!r} — must look like '<50ms', '>=99%', '==0'"
        )
    op = m.group("op")
    threshold = float(m.group("num"))
    unit = m.group("unit") or ""
    return op, threshold, unit


def compare(observed: float, op: str, threshold: float) -> bool:
    """Return True iff ``observed <op> threshold`` holds.

    Raises ``ValueError`` for an unknown ``op``.
    """
    if op == "<":
        return observed < threshold
    if op == "<=":
        return observed <= threshold
    if op == ">":
        return observed > threshold
    if op == ">=":
        return observed >= threshold
    if op == "==":
        return observed == threshold
    if op == "!=":
        return observed != threshold
    raise ValueError(f"unknown comparison operator {op!r}")


def is_trending(observed: float, op: str, threshold: float, margin: float = 0.1) -> bool:
    """Return True iff ``observed`` is within ``margin`` of the threshold in the
    "right" direction for ``op`` but does not yet satisfy the comparison.

    ``margin`` defaults to 0.1 (10%). For ``op == "=="`` or ``"!="`` the concept of
    direction is ambiguous; we say "trending" if the observed value is within
    ``margin`` of the threshold (relative).
    """
    if compare(observed, op, threshold):
        return False  # already met → not "trending"

    # Compute the absolute slack zone size; relative to threshold (with a
    # tiny floor so a zero threshold doesn't reduce the margin to nothing).
    base = max(abs(threshold), 1e-9)
    slack = base * margin

    if op in ("<", "<="):
        # We want observed below threshold. Trending if we overshot by < margin.
        return observed - threshold <= slack
    if op in (">", ">="):
        # We want observed above threshold. Trending if we are short by < margin.
        return threshold - observed <= slack
    if op in ("==", "!="):
        return abs(observed - threshold) <= slack
    return False


__all__ = ["compare", "is_trending", "parse_expect"]
