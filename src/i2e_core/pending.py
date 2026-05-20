"""Pending-file IO for async providers.

A pending file is a small YAML document written under ``.i2e/pending/`` when an
async provider (``human``, ``survey``, ``interview``, etc.) needs to ask a
human a question. The orchestrator's preflight pass picks up files whose
``status: resolved`` and applies the resolution before the next run.

This module is reused by every async provider — we keep the IO surface narrow:

- ``PendingFile`` — Pydantic model
- ``pending_filename`` — derive the canonical basename
- ``write_pending`` — atomic create; raises ``FileExistsError`` on conflict
- ``read_pending`` — load + validate
- ``list_open_pending`` / ``list_resolved_pending``
- ``archive_pending`` — atomic move to ``.i2e/logs/``
- ``resolve_to_verdict`` — translate a resolved pending file into an ItemVerdict
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .evidence import ItemVerdict
from .io_utils import atomic_write, dump_yaml, load_yaml
from .paths import logs_dir, pending_dir


class PendingFile(BaseModel):
    """The on-disk pending document. Optional fields stay absent when unused."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["open", "resolved"] = "open"
    kind: Literal["escalation", "human_evaluation"]
    capability: str
    item_id: str
    asked_at: datetime | None = None
    escalated_at: datetime | None = None
    reason: str | None = None
    expect: str | None = None
    observed: str | None = None
    attempts: list[dict[str, Any]] = Field(default_factory=list)
    ask: str
    verdict_options: list[str] | None = None
    resolution: str | None = None


def _date_prefix(when: datetime | None) -> str:
    if when is None:
        when = datetime.utcnow()
    return when.strftime("%Y-%m-%d")


def pending_filename(
    capability: str,
    item_id: str,
    when: datetime | None = None,
) -> str:
    """Return ``YYYY-MM-DD-<capability>-<item-id>.yaml``."""
    return f"{_date_prefix(when)}-{capability}-{item_id}.yaml"


def _model_to_yaml_dict(pf: PendingFile) -> dict[str, Any]:
    # ``mode="json"`` serializes datetimes as ISO 8601 strings — predictable
    # round-tripping and human-editable.
    return pf.model_dump(mode="json", exclude_none=False)


def write_pending(root: Path, pf: PendingFile) -> Path:
    """Atomically write a pending file. Raises ``FileExistsError`` if present."""
    pdir = pending_dir(Path(root))
    pdir.mkdir(parents=True, exist_ok=True)
    when = pf.asked_at or pf.escalated_at
    fname = pending_filename(pf.capability, pf.item_id, when)
    target = pdir / fname
    if target.exists():
        raise FileExistsError(
            f"Pending file already exists for {pf.capability}/{pf.item_id}: {target}"
        )
    atomic_write(target, dump_yaml(_model_to_yaml_dict(pf)))
    return target


def read_pending(path: Path) -> PendingFile:
    """Load + validate a pending file."""
    data = load_yaml(Path(path)) or {}
    return PendingFile.model_validate(data)


def _list_pending_with_status(
    root: Path, status: Literal["open", "resolved"]
) -> list[Path]:
    pdir = pending_dir(Path(root))
    if not pdir.exists():
        return []
    out: list[Path] = []
    for p in sorted(pdir.iterdir()):
        if p.suffix != ".yaml" or not p.is_file():
            continue
        try:
            pf = read_pending(p)
        except Exception:
            # Skip unparseable files — operator can clean them up by hand.
            continue
        if pf.status == status:
            out.append(p)
    return out


def list_open_pending(root: Path) -> list[Path]:
    """Return pending file paths whose ``status: open``."""
    return _list_pending_with_status(Path(root), "open")


def list_resolved_pending(root: Path) -> list[Path]:
    """Return pending file paths whose ``status: resolved``."""
    return _list_pending_with_status(Path(root), "resolved")


def archive_pending(root: Path, path: Path) -> Path:
    """Atomically move a pending file into ``.i2e/logs/``.

    Uses ``os.replace`` which is atomic on Windows and POSIX. If the destination
    already exists it is overwritten (logs are append-only by convention; we
    don't expect collisions in practice).
    """
    root = Path(root)
    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(f"Pending file not found: {src}")
    ldir = logs_dir(root)
    ldir.mkdir(parents=True, exist_ok=True)
    dest = ldir / src.name
    os.replace(src, dest)
    return dest


def _try_numeric(s: str) -> float | None:
    """Return ``float(s)`` if ``s`` parses cleanly as a number, else ``None``."""
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def resolve_to_verdict(pf: PendingFile) -> ItemVerdict:
    """Translate a resolved pending file into an ``ItemVerdict``.

    For ``kind="human_evaluation"``:

    - ``resolution == "yes"`` → ``ItemVerdict(verdict="pass", ...)``
    - ``resolution in {"no", "partial"}`` → ``ItemVerdict(verdict="fail", ...)``
    - **numeric** resolution (e.g. ``"9"``) combined with a comparison
      ``expect`` (e.g. ``">=8"``) — emit a Target-shape verdict:
      ``met`` iff the comparison holds, otherwise ``unmet``.

    Raises ``ValueError`` if the pending file is not actually resolved or if
    the resolution is missing / unrecognised.
    """
    if pf.status != "resolved":
        raise ValueError(
            f"resolve_to_verdict called on a non-resolved pending file "
            f"(status={pf.status!r})"
        )
    if pf.kind != "human_evaluation":
        raise ValueError(
            f"resolve_to_verdict only handles kind='human_evaluation' for now; "
            f"got kind={pf.kind!r} (escalations are an adapt concern)"
        )
    now = datetime.now(timezone.utc)
    raw_resolution = (pf.resolution or "").strip()
    resolution = raw_resolution.lower()

    # Numeric (survey) branch — kicks in when the resolution parses as a number
    # AND ``expect`` is a comparison expression. Surveys flow through this
    # branch; the legacy human yes/no flow falls through to the literal match
    # below.
    numeric_value = _try_numeric(raw_resolution)
    if numeric_value is not None:
        expect = (pf.expect or "").strip()
        if expect:
            # Lazy import to keep the pending module decoupled from provider.
            from .provider.expect_parser import compare, parse_expect

            try:
                op, threshold, _unit = parse_expect(expect)
            except ValueError:
                # Not a comparison expression — fall through to literal-match.
                op = None  # type: ignore[assignment]
            else:
                value_str = (
                    str(int(numeric_value))
                    if numeric_value.is_integer()
                    else str(numeric_value)
                )
                if compare(numeric_value, op, threshold):
                    return ItemVerdict(
                        verdict="met",
                        value=value_str,
                        last_observed=now,
                    )
                return ItemVerdict(
                    verdict="unmet",
                    value=value_str,
                    last_observed=now,
                    raw={"resolution": pf.resolution},
                )

    # Legacy yes / no / partial branch.
    if resolution == "yes":
        return ItemVerdict(verdict="pass", last_observed=now)
    if resolution in {"no", "partial"}:
        return ItemVerdict(
            verdict="fail",
            last_observed=now,
            raw={"resolution": pf.resolution},
        )
    raise ValueError(
        f"Unrecognised resolution {pf.resolution!r} for human_evaluation "
        f"pending file {pf.capability}/{pf.item_id}"
    )


__all__ = [
    "PendingFile",
    "archive_pending",
    "list_open_pending",
    "list_resolved_pending",
    "pending_filename",
    "read_pending",
    "resolve_to_verdict",
    "write_pending",
]
