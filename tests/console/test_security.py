"""Constraints:

- i2e-serve binds 127.0.0.1 only (console-foundation).
- Console write actions never touch anything outside the carve-out
  (console-intent-and-writes).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from i2e_core.console.actions.promote import promote
from i2e_core.console.actions.resolve import resolve
from i2e_core.intent import Capability, EvidenceItem, Frontmatter, write_intent
from i2e_core.pending import PendingFile, write_pending
from i2e_core.serve import start_server


def test_binds_127_0_0_1_only(tmp_path):
    with pytest.raises(ValueError, match="127.0.0.1"):
        start_server(root=tmp_path, host="0.0.0.0", port=0, open_browser=False)


def _snapshot(root: Path) -> dict[Path, bytes]:
    """Return path → content for every file under ``root``."""
    out: dict[Path, bytes] = {}
    for p in root.rglob("*"):
        if p.is_file():
            out[p.relative_to(root)] = p.read_bytes()
    return out


def _seed_draft_and_pending(root: Path) -> tuple[Path, Path]:
    intents = root / ".i2e" / "intents"
    intents.mkdir(parents=True, exist_ok=True)
    today = date.today()
    cap = Capability(
        frontmatter=Frontmatter(
            capability="demo-cap",
            created=today,
            updated=today,
            version=1,
            status="draft",
            watcher="@me",
        ),
        description="demo",
        evidence=[
            EvidenceItem(
                id="demo-case",
                type="case",
                provider="pytest",
                query="tests/test_demo.py::test_x",
                expect="passes",
            )
        ],
    )
    intent_path = write_intent(cap, intents / "demo-cap.md")
    pending_path = write_pending(
        root,
        PendingFile(
            kind="human_evaluation",
            capability="demo-cap",
            item_id="demo-target",
            asked_at=datetime(2026, 5, 21, 14, 0, 0, tzinfo=timezone.utc),
            ask="Render check?",
            expect="yes",
            verdict_options=["yes", "no", "partial"],
        ),
    )
    return intent_path, pending_path


def test_no_writes_outside_boundary(tmp_path):
    intent_path, pending_path = _seed_draft_and_pending(tmp_path)
    before = _snapshot(tmp_path)

    # The two narrow console writes.
    result = promote(tmp_path, "demo-cap")
    assert result["valid"] is True
    resolve(tmp_path, pending_path.name, verdict="yes", notes="ok")

    after = _snapshot(tmp_path)

    # Set of files that changed (different content, added, or removed).
    changed: set[Path] = set()
    for rel in set(before) | set(after):
        if before.get(rel) != after.get(rel):
            changed.add(rel)

    # Only the two carve-out paths may appear.
    allowed = {
        intent_path.relative_to(tmp_path),
        pending_path.relative_to(tmp_path),
    }
    extra = changed - allowed
    assert not extra, f"console wrote outside the carve-out: {sorted(extra)}"
