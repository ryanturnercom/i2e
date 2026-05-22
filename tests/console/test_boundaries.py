"""Boundary rule enforcement — console writes nothing outside the carve-out.

The carve-out is:

- ``.i2e/intents/<slug>.md``: ``status`` frontmatter field only
- ``.i2e/pending/<file>.yaml``: ``resolution`` (and ``status``) only

These tests pin the carve-out so a future refactor that widens what
the console writes will break a test before it ships.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import yaml

from i2e_core.console.actions.promote import promote
from i2e_core.console.actions.resolve import resolve
from i2e_core.intent import Capability, EvidenceItem, Frontmatter, write_intent
from i2e_core.pending import PendingFile, write_pending


def _make_draft(root: Path, slug: str = "demo-cap") -> Path:
    intents = root / ".i2e" / "intents"
    intents.mkdir(parents=True, exist_ok=True)
    today = date.today()
    cap = Capability(
        frontmatter=Frontmatter(
            capability=slug,
            created=today,
            updated=today,
            version=1,
            status="draft",
            watcher="@ryan",
            depends_on=[],
            touches=["src/x/**"],
        ),
        description="demo body",
        evidence=[
            EvidenceItem(
                id=f"{slug}-case",
                type="case",
                provider="pytest",
                query=f"tests/test_{slug}.py::test_x",
                expect="passes",
            )
        ],
    )
    return write_intent(cap, intents / f"{slug}.md")


def _parse_frontmatter(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    assert raw.startswith("---\n")
    end = raw.index("\n---\n", 4)
    return yaml.safe_load(raw[4:end]) or {}


def test_console_only_writes_status_field(tmp_path):
    path = _make_draft(tmp_path, "demo-cap")
    before = _parse_frontmatter(path)
    body_before = path.read_text(encoding="utf-8").split("\n---\n", 1)[1]

    result = promote(tmp_path, "demo-cap")
    assert result["valid"] is True

    after = _parse_frontmatter(path)
    body_after = path.read_text(encoding="utf-8").split("\n---\n", 1)[1]

    # Body untouched.
    assert body_before == body_after

    # Status flipped; everything else (other than the updated timestamp
    # and version bump rules from intent_authoring.save) must be byte
    # identical to before. Compare the entrenched fields.
    assert before["status"] == "draft"
    assert after["status"] == "active"
    for key in ("capability", "watcher", "depends_on", "touches", "spec", "spec_section"):
        if key in before or key in after:
            assert before.get(key) == after.get(key), (
                f"console promote unexpectedly modified frontmatter field {key!r}"
            )


def test_console_only_writes_resolution_block(tmp_path):
    pf = PendingFile(
        kind="human_evaluation",
        capability="demo-cap",
        item_id="demo-target",
        asked_at=datetime(2026, 5, 21, 14, 0, 0, tzinfo=timezone.utc),
        ask="Render check?",
        expect="yes",
        verdict_options=["yes", "no", "partial"],
        url="http://example/x",
        steps=["step 1", "step 2"],
    )
    path = write_pending(tmp_path, pf)

    before = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    resolve(tmp_path, path.name, verdict="yes", notes="all good")

    after = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    # status flipped open → resolved; resolution populated.
    assert before["status"] == "open"
    assert after["status"] == "resolved"
    assert before.get("resolution") in (None, "")
    assert after["resolution"] and "yes" in after["resolution"]

    # Every other field must be byte-identical.
    for key in set(before) | set(after):
        if key in ("status", "resolution"):
            continue
        assert before.get(key) == after.get(key), (
            f"console resolve unexpectedly modified pending field {key!r}"
        )
