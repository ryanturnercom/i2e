"""Run-id generator and parser."""

from __future__ import annotations

import re
import secrets
from datetime import date, datetime, timezone

RUN_ID_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-([0-9a-f]{6})$")


def new_run_id(now: datetime | None = None) -> str:
    """Return ``YYYY-MM-DD-<6hex>``."""
    ts = now or datetime.now(timezone.utc)
    return f"{ts:%Y-%m-%d}-{secrets.token_hex(3)}"


def parse_run_id(s: str) -> tuple[date, str]:
    """Split a run-id into (date, hex-suffix); raises ValueError if malformed."""
    m = RUN_ID_RE.match(s)
    if not m:
        raise ValueError(f"Invalid run-id: {s!r}")
    y, mo, d, suffix = m.groups()
    return date(int(y), int(mo), int(d)), suffix
