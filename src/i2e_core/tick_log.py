"""Tick-log writer + reader (spec §9).

Append-only, dated, signal-only — empty ticks don't log. Each orchestrator
tick that DID something writes ``<tick_id>-tick.yaml`` into ``.i2e/logs/``.
``i2e-adapt`` reads this history to fill in the "what changed" column on an
escalation's attempts list.

Action strings follow a stable grammar so they're greppable. The grammar
matters because :func:`latest_tick_for` and :func:`changes_since` are
literal substring scans over action lines. Use these shapes when the
orchestrator records actions:

- ``applied_resolution: <cap> / <item>``
- ``ran_develop: <cap> (intent v<a> -> v<b>)``
- ``ran_evidence: <cap> (<summary>)``
- ``ran_adapt: <cap> (retries=N, escalations=M)``
- ``new_approach: <cap> / <item> — <text>``  (resolution option 2)

The orchestrator (epic 07) is the only writer. Adapt and evidence record
their summaries via the orchestrator's tick.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .io_utils import atomic_write, dump_yaml, load_yaml
from .paths import logs_dir


_TICK_GLOB = "*-tick.yaml"


class TickLog(BaseModel):
    """One orchestrator tick that performed at least one action."""

    model_config = ConfigDict(extra="forbid")

    tick_id: str
    ran_at: datetime
    actions: list[str] = Field(default_factory=list)


def _tick_path(root: Path, tick_id: str) -> Path:
    return logs_dir(Path(root)) / f"{tick_id}-tick.yaml"


def write_tick(root: Path, tick: TickLog) -> Path | None:
    """Persist a tick log.

    - Empty ``actions`` ⇒ return ``None``, write nothing (spec §9: empty
      ticks don't log).
    - Non-empty ⇒ atomic write; refuses to overwrite an existing file
      (tick logs are immutable).
    """
    if not tick.actions:
        return None
    p = _tick_path(root, tick.tick_id)
    if p.exists():
        raise FileExistsError(f"Tick log already exists: {p}")
    payload = tick.model_dump(mode="json")
    p.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(p, dump_yaml(payload))
    return p


def _read_tick(path: Path) -> TickLog | None:
    """Best-effort load — corrupt or stale files are ignored, not fatal."""
    try:
        data = load_yaml(path) or {}
        return TickLog.model_validate(data)
    except Exception:
        return None


def _ticks_newest_first(root: Path) -> list[tuple[Path, TickLog]]:
    """Return all parseable tick logs sorted newest-first by mtime."""
    base = logs_dir(Path(root))
    if not base.exists():
        return []
    candidates = sorted(
        (p for p in base.glob(_TICK_GLOB) if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    out: list[tuple[Path, TickLog]] = []
    for p in candidates:
        tl = _read_tick(p)
        if tl is not None:
            out.append((p, tl))
    return out


def _action_mentions(action: str, capability: str, item_id: str | None) -> bool:
    """Substring scan: action must mention ``capability`` (and ``item_id`` if given)."""
    if capability not in action:
        return False
    if item_id is not None and item_id not in action:
        return False
    return True


def latest_tick_for(
    root: Path,
    capability: str,
    item_id: str | None = None,
) -> TickLog | None:
    """Newest tick log whose ``actions`` mention ``capability`` (+ ``item_id``)."""
    for _, tl in _ticks_newest_first(root):
        for action in tl.actions:
            if _action_mentions(action, capability, item_id):
                return tl
    return None


# Tokens we strip from an action string when building a "change description".
# Keep the regex anchored to whole-word matches so we don't munch capability
# slugs that happen to contain another item's id.
_PREFIX_LABELS = (
    "applied_resolution",
    "ran_develop",
    "ran_evidence",
    "ran_adapt",
    "new_approach",
)


def _extract_change_description(
    action: str, capability: str, item_id: str
) -> str:
    """Action string ⇒ short change description.

    Drops the leading ``<label>:`` token and the ``<cap>``/``<item>``
    occurrences so the remainder reads like a delta. If nothing meaningful
    is left, returns the original action.
    """
    s = action
    # Strip a leading "label:" if present.
    for label in _PREFIX_LABELS:
        if s.startswith(f"{label}:"):
            s = s[len(label) + 1 :].lstrip()
            break
    # Remove capability and item-id tokens (whole-word style — common
    # separators are ``/``, spaces, parens, em-dash).
    for token in (capability, item_id):
        s = re.sub(rf"(?<![A-Za-z0-9_-]){re.escape(token)}(?![A-Za-z0-9_-])", "", s)
    # Collapse leftover separators.
    s = re.sub(r"\s*/\s*", " ", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" -—:")
    return s or action


def changes_since(
    root: Path,
    capability: str,
    item_id: str,
    n: int = 3,
) -> list[tuple[str, str]]:
    """Return up to ``n`` ``(tick_id, change_description)`` pairs, newest first.

    Walks tick logs newest-first by mtime; for each tick, returns the first
    action that mentions both ``capability`` and ``item_id``. Used by
    :func:`i2e_core.adapt.escalate` to fill out the ``attempts`` block on an
    escalation pending file.
    """
    out: list[tuple[str, str]] = []
    for _, tl in _ticks_newest_first(root):
        for action in tl.actions:
            if _action_mentions(action, capability, item_id):
                desc = _extract_change_description(action, capability, item_id)
                out.append((tl.tick_id, desc))
                break
        if len(out) >= n:
            break
    return out


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


__all__ = [
    "TickLog",
    "changes_since",
    "latest_tick_for",
    "write_tick",
]
