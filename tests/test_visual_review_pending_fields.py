"""Visual-review fields on EvidenceItem, PendingFile, and the human provider."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from i2e_core.config import default_config
from i2e_core.intent import Constraint, EvidenceItem, parse_intent
from i2e_core.paths import pending_dir
from i2e_core.pending import (
    PendingFile,
    read_pending,
    resolve_to_verdict,
    write_pending,
)
from i2e_core.provider import AsyncResult, ProviderContext
from i2e_core.provider.discovery import clear_cache, load_provider
from i2e_core.runid import new_run_id

REAL_SKILLS_DIR = Path(__file__).resolve().parents[1] / ".claude" / "skills"


def _provider_ctx(tmp_path: Path, capability: str = "visual-demo") -> ProviderContext:
    for sub in ("pending", "logs", "evidence", "intents", "context"):
        (tmp_path / ".i2e" / sub).mkdir(parents=True, exist_ok=True)
    return ProviderContext(
        root=tmp_path,
        capability=capability,
        run_id=new_run_id(),
        cfg=default_config(),
    )


def test_evidence_item_accepts_url_steps_screenshot() -> None:
    item = EvidenceItem(
        id="visual-check",
        type="target",
        provider="human",
        query="Confirm the checkout flow renders correctly.",
        expect="yes",
        url="http://localhost:3000/checkout",
        steps=[
            "Open the URL on desktop width",
            "Add two items to the cart",
            "Confirm the totals row stays right-aligned",
        ],
        screenshot="docs/screenshots/checkout-baseline.png",
    )
    assert item.url == "http://localhost:3000/checkout"
    assert item.steps and len(item.steps) == 3
    assert item.steps[1] == "Add two items to the cart"
    assert item.screenshot == "docs/screenshots/checkout-baseline.png"


def test_pending_file_carries_visual_fields(tmp_path: Path) -> None:
    (tmp_path / ".i2e").mkdir()
    pf = PendingFile(
        kind="human_evaluation",
        capability="cap",
        item_id="visual",
        asked_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
        ask="Look at the page.",
        expect="yes",
        url="http://localhost:3000/page",
        steps=["Open URL", "Look at the header"],
        screenshot="ref.png",
    )
    path = write_pending(tmp_path, pf)
    loaded = read_pending(path)
    assert loaded.url == "http://localhost:3000/page"
    assert loaded.steps == ["Open URL", "Look at the header"]
    assert loaded.screenshot == "ref.png"


def test_human_provider_copies_visual_fields_onto_pending(tmp_path: Path) -> None:
    clear_cache()
    ctx = _provider_ctx(tmp_path)
    provider = load_provider("human", extra_paths=[REAL_SKILLS_DIR])

    item = EvidenceItem(
        id="page-vibe",
        type="target",
        provider="human",
        query="Does the page feel right?",
        expect="yes",
        url="http://localhost:3000/feed",
        steps=["Open URL", "Scroll", "Confirm cards stack vertically"],
        screenshot="baseline.png",
    )
    result = provider.invoke(item, ctx)
    assert isinstance(result, AsyncResult)
    assert result.verdict == "awaiting_human"

    written = pending_dir(tmp_path) / result.pending
    pf = read_pending(written)
    assert pf.url == "http://localhost:3000/feed"
    assert pf.steps == ["Open URL", "Scroll", "Confirm cards stack vertically"]
    assert pf.screenshot == "baseline.png"
    # And the legacy ask text still lands too — visual fields are additive.
    assert pf.ask == "Does the page feel right?"


def test_existing_intents_without_visual_fields_still_parse(tmp_path: Path) -> None:
    intent_path = tmp_path / "legacy.md"
    intent_path.write_text(
        "---\n"
        "capability: legacy\n"
        "created: 2026-05-19\n"
        "updated: 2026-05-19\n"
        "version: 1\n"
        "status: active\n"
        "watcher: '@me'\n"
        "---\n"
        "\n"
        "A legacy intent without the new fields.\n"
        "\n"
        "## Evidence of success\n"
        "\n"
        "- id: a-case\n"
        "  type: case\n"
        "  provider: pytest\n"
        "  query: tests/test_x.py\n"
        "  expect: passes\n"
        "  effort: medium\n"
        "\n"
        "## Constraints\n",
        encoding="utf-8",
    )
    cap = parse_intent(intent_path)
    assert cap.evidence[0].id == "a-case"
    assert cap.evidence[0].url is None
    assert cap.evidence[0].steps is None
    assert cap.evidence[0].screenshot is None


def test_visual_target_blocks_shippable_until_human_resolves(tmp_path: Path) -> None:
    clear_cache()
    ctx = _provider_ctx(tmp_path, capability="visual-block")
    provider = load_provider("human", extra_paths=[REAL_SKILLS_DIR])

    item = EvidenceItem(
        id="visual-target",
        type="target",
        provider="human",
        query="Looks right?",
        expect="yes",
        url="http://localhost:3000/foo",
    )

    # First invoke → pending file written, verdict is awaiting_human (the
    # block signal the orchestrator honours when computing Shippable).
    result = provider.invoke(item, ctx)
    assert result.verdict == "awaiting_human"

    # Pending file is open and unresolved; resolve_to_verdict refuses to
    # produce a pass/met verdict from it.
    pending_path = pending_dir(tmp_path) / result.pending
    pf = read_pending(pending_path)
    assert pf.status == "open"
    assert pf.resolution is None
    with pytest.raises(ValueError):
        resolve_to_verdict(pf)

    # Once the human flips status=resolved + resolution=yes, we get a met
    # verdict (a human item is always a target).
    pf_resolved = pf.model_copy(update={"status": "resolved", "resolution": "yes"})
    verdict = resolve_to_verdict(pf_resolved)
    assert verdict.verdict == "met"


def test_visual_fields_default_to_absent() -> None:
    item = EvidenceItem(
        id="basic",
        type="case",
        provider="pytest",
        query="tests/foo.py",
        expect="passes",
    )
    assert item.url is None
    assert item.steps is None
    assert item.screenshot is None

    cn = Constraint(
        id="basic-c",
        provider="pytest",
        query="tests/foo.py",
        expect="passes",
    )
    assert cn.url is None
    assert cn.steps is None
    assert cn.screenshot is None
