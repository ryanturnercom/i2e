"""Console promote action — gate-validated draft → active flip."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from i2e_core.console.actions.promote import promote
from i2e_core.intent import Capability, EvidenceItem, Frontmatter, parse_intent, write_intent


def _write_intent(root: Path, slug: str, evidence: list[EvidenceItem]) -> Path:
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
            watcher="@me",
        ),
        description="demo",
        evidence=evidence,
    )
    return write_intent(cap, intents / f"{slug}.md")


def test_blocks_invalid_intent(tmp_path):
    # No evidence + no constraints = forced-evidence rule 3 violation.
    path = _write_intent(tmp_path, "bad-cap", evidence=[])
    # Patch the file on disk to remove evidence (write_intent + the model
    # both insist on at least one item via Pydantic, but the gate is the
    # canonical check at promote time).
    # Use an evidence list whose provider is unknown so the gate fires.
    path = _write_intent(
        tmp_path,
        "bad-cap",
        evidence=[
            EvidenceItem(
                id="bad-case",
                type="case",
                provider="madeup-provider",
                query="tests/x.py::test_y",
                expect="passes",
            )
        ],
    )

    result = promote(tmp_path, "bad-cap")
    assert result["valid"] is False
    assert "errors" in result
    assert len(result["errors"]) > 0

    # Status stays draft on disk.
    assert parse_intent(path).frontmatter.status == "draft"


def test_allows_valid_intent(tmp_path):
    path = _write_intent(
        tmp_path,
        "good-cap",
        evidence=[
            EvidenceItem(
                id="good-case",
                type="case",
                provider="pytest",
                query="tests/x.py::test_y",
                expect="passes",
            )
        ],
    )

    result = promote(tmp_path, "good-cap")
    assert result["valid"] is True
    assert result["new_status"] == "active"
    assert result["old_status"] == "draft"

    # Status flipped on disk.
    assert parse_intent(path).frontmatter.status == "active"
