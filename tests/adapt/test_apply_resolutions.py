"""Tests for :func:`i2e_core.adapt.apply_resolutions`."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from i2e_core.adapt import apply_resolutions, escalate
from i2e_core.evidence import read_current
from i2e_core.intent import parse_intent
from i2e_core.paths import intents_dir, logs_dir, pending_dir
from i2e_core.pending import PendingFile, read_pending, write_pending


def _intent(write_intent):
    return write_intent(
        "shorten-url",
        evidence=[
            {
                "id": "usage-growth",
                "type": "target",
                "provider": "datadog",
                "query": "qoq",
                "expect": "+10%",
                "effort": "low",
            },
            {
                "id": "code-generated",
                "type": "case",
                "provider": "pytest",
                "query": "tests/x.py::test_y",
                "expect": "passes",
                "effort": "medium",
            },
        ],
        constraints=[
            {
                "id": "no-open-redirect",
                "provider": "pytest",
                "query": "tests/adv.py",
                "expect": "passes",
                "effort": "high",
            },
        ],
        version=2,
    )


def _seed_resolved(
    project: Path, item_id: str, resolution: str
) -> Path:
    """Seed a resolved escalation pending file for ``item_id``."""
    pf = PendingFile(
        status="resolved",
        kind="escalation",
        capability="shorten-url",
        item_id=item_id,
        escalated_at=datetime.now(timezone.utc),
        ask="pick one",
        resolution=resolution,
    )
    return write_pending(project, pf)


def _seed_human_resolved(
    project: Path, item_id: str, resolution: str
) -> Path:
    """Seed a resolved human_evaluation pending file for ``item_id``."""
    pf = PendingFile(
        status="resolved",
        kind="human_evaluation",
        capability="shorten-url",
        item_id=item_id,
        asked_at=datetime.now(timezone.utc),
        ask="does it work?",
        resolution=resolution,
        verdict_options=["yes", "no", "partial"],
    )
    return write_pending(project, pf)


def test_option_1_loosen_updates_expect_and_bumps_version(
    project, write_intent, write_current_for
):
    intent_path = _intent(write_intent)
    write_current_for(
        "shorten-url",
        {"usage-growth": {"verdict": "trending", "attempts_used": 1}},
        intent_version=2,
    )
    pp = _seed_resolved(
        project, "usage-growth", "1) loosen\nnew expect: +5%"
    )

    applied = apply_resolutions(project)
    assert len(applied) == 1
    res = applied[0]
    assert res.choice == 1
    assert res.intent_changed is True

    cap = parse_intent(intent_path)
    item = next(it for it in cap.evidence if it.id == "usage-growth")
    assert item.expect == "+5%"
    assert cap.frontmatter.version == 3
    # Pending moved.
    assert not pp.exists()
    assert (logs_dir(project) / pp.name).exists()


def test_option_1_without_new_expect_raises_or_skips(
    project, write_intent, write_current_for
):
    _intent(write_intent)
    write_current_for(
        "shorten-url",
        {"usage-growth": {"verdict": "trending", "attempts_used": 1}},
        intent_version=2,
    )
    # No "new expect:" line — must error out at the helper, and the
    # batch-applier treats this as a per-file failure (file stays in place).
    pp = _seed_resolved(project, "usage-growth", "1) loosen")
    applied = apply_resolutions(project)
    assert applied == []
    # Pending file must still exist (no silent intent edit).
    assert pp.exists()

    # The error must be reachable through the helper directly too.
    from i2e_core.adapt import _apply_loosen

    cap = parse_intent(intents_dir(project) / "shorten-url.md")
    with pytest.raises(ValueError):
        _apply_loosen(project, cap, "usage-growth", "1) loosen")


def test_option_2_new_approach_resets_attempts_used(
    project, write_intent, write_current_for
):
    intent_path = _intent(write_intent)
    write_current_for(
        "shorten-url",
        {"usage-growth": {"verdict": "trending", "attempts_used": 3}},
        intent_version=2,
    )
    pp = _seed_resolved(
        project, "usage-growth", "2) new approach\nTry shipping a referral feature"
    )
    applied = apply_resolutions(project)
    assert len(applied) == 1
    assert applied[0].choice == 2
    assert applied[0].intent_changed is False

    cap = parse_intent(intent_path)
    # Intent untouched — version stays at 2.
    assert cap.frontmatter.version == 2

    current = read_current(project, "shorten-url")
    assert current is not None
    item = current.items["usage-growth"]
    assert item.attempts_used == 0
    assert "new_approach" in item.raw
    assert "referral" in item.raw["new_approach"].lower()
    # Pending archived.
    assert not pp.exists()
    assert (logs_dir(project) / pp.name).exists()


def test_option_3_retire_removes_item_and_bumps_version(
    project, write_intent, write_current_for
):
    intent_path = _intent(write_intent)
    write_current_for(
        "shorten-url",
        {"usage-growth": {"verdict": "unmet", "attempts_used": 5}},
        intent_version=2,
    )
    pp = _seed_resolved(project, "usage-growth", "3) retire")
    applied = apply_resolutions(project)
    assert len(applied) == 1
    assert applied[0].choice == 3
    assert applied[0].intent_changed is True

    cap = parse_intent(intent_path)
    assert all(it.id != "usage-growth" for it in cap.evidence)
    assert cap.frontmatter.version == 3
    assert not pp.exists()


def test_option_3_retire_constraint(
    project, write_intent, write_current_for
):
    intent_path = _intent(write_intent)
    write_current_for(
        "shorten-url",
        {"no-open-redirect": {"verdict": "fail", "attempts_used": 99}},
        intent_version=2,
    )
    _seed_resolved(project, "no-open-redirect", "retire")
    applied = apply_resolutions(project)
    assert len(applied) == 1
    assert applied[0].choice == 3
    cap = parse_intent(intent_path)
    assert all(it.id != "no-open-redirect" for it in cap.constraints)


def test_option_4_accept_case_pass(
    project, write_intent, write_current_for
):
    intent_path = _intent(write_intent)
    write_current_for(
        "shorten-url",
        {"code-generated": {"verdict": "fail", "attempts_used": 6}},
        intent_version=2,
    )
    _seed_resolved(project, "code-generated", "4) accept")
    applied = apply_resolutions(project)
    assert len(applied) == 1
    assert applied[0].choice == 4
    assert applied[0].intent_changed is False

    current = read_current(project, "shorten-url")
    assert current.items["code-generated"].verdict == "pass"
    # Intent unchanged.
    cap = parse_intent(intent_path)
    assert cap.frontmatter.version == 2


def test_option_4_accept_target_met(
    project, write_intent, write_current_for
):
    _intent(write_intent)
    write_current_for(
        "shorten-url",
        {"usage-growth": {"verdict": "trending", "attempts_used": 3}},
        intent_version=2,
    )
    _seed_resolved(project, "usage-growth", "4")
    applied = apply_resolutions(project)
    assert len(applied) == 1
    assert applied[0].choice == 4
    current = read_current(project, "shorten-url")
    assert current.items["usage-growth"].verdict == "met"


def test_choice_parser_forgiveness(
    project, write_intent, write_current_for
):
    """Confirm the parser accepts the documented input shapes."""
    from i2e_core.adapt import _parse_choice

    assert _parse_choice("1") == 1
    assert _parse_choice("1.") == 1
    assert _parse_choice("1)") == 1
    assert _parse_choice("option 1") == 1
    assert _parse_choice("Loosen the target a bit") == 1
    assert _parse_choice("2 — try X") == 2
    assert _parse_choice("new approach") == 2
    assert _parse_choice("3. retire please") == 3
    assert _parse_choice("Retire this") == 3
    assert _parse_choice("Accept current state") == 4
    assert _parse_choice("4") == 4
    with pytest.raises(ValueError):
        _parse_choice("")
    with pytest.raises(ValueError):
        _parse_choice("¯\\_(ツ)_/¯")


def test_unparseable_resolution_skipped(
    project, write_intent, write_current_for
):
    _intent(write_intent)
    write_current_for(
        "shorten-url",
        {"usage-growth": {"verdict": "fail", "attempts_used": 5}},
        intent_version=2,
    )
    pp = _seed_resolved(project, "usage-growth", "I don't know")
    applied = apply_resolutions(project)
    assert applied == []
    # Stays put for the operator.
    assert pp.exists()


def test_batch_applies_multiple_files(
    project, write_intent, write_current_for
):
    _intent(write_intent)
    write_current_for(
        "shorten-url",
        {
            "usage-growth": {"verdict": "trending", "attempts_used": 3},
            "code-generated": {"verdict": "fail", "attempts_used": 6},
        },
        intent_version=2,
    )
    _seed_resolved(
        project, "usage-growth", "1) loosen\nnew expect: +3%"
    )
    _seed_resolved(project, "code-generated", "4) accept")
    applied = apply_resolutions(project)
    assert len(applied) == 2
    choices = {a.choice for a in applied}
    assert choices == {1, 4}


def test_end_to_end_plan_escalate_apply(
    project, write_intent, write_current_for
):
    """Integration: plan → escalate → human resolves → apply_resolutions."""
    from i2e_core.adapt import plan as adapt_plan

    intent_path = _intent(write_intent)
    write_current_for(
        "shorten-url",
        {"usage-growth": {"verdict": "trending", "attempts_used": 1}},
        intent_version=2,
    )
    # 1. Plan says: escalate this item (low target, attempts_used=1, max=1).
    pl = adapt_plan(project, "shorten-url")
    assert len(pl.escalations) == 1
    target_item = pl.escalations[0].item_id

    # 2. Adapt writes a pending file.
    pp = escalate(project, "shorten-url", target_item)
    assert pp.exists()

    # 3. Human resolves it.
    pf = read_pending(pp)
    pf.status = "resolved"
    pf.resolution = "1) loosen\nnew expect: +5%"
    pp.write_text(
        __import__("yaml").safe_dump(pf.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )

    # 4. Orchestrator applies on next preflight.
    applied = apply_resolutions(project)
    assert len(applied) == 1
    assert applied[0].choice == 1
    cap = parse_intent(intent_path)
    item = next(it for it in cap.evidence if it.id == target_item)
    assert item.expect == "+5%"


# ── human_evaluation resolutions (yes/no/partial → verdict) ──────────────────


def test_human_evaluation_yes_with_notes_resolves_to_pass(
    project, write_intent, write_current_for
):
    _intent(write_intent)
    write_current_for(
        "shorten-url",
        {"code-generated": {"verdict": "awaiting_human", "attempts_used": 2}},
        intent_version=2,
    )
    # The console resolve form writes "<verdict>\n\n<notes>" — the appended
    # note must not break the yes/no/partial match.
    pp = _seed_human_resolved(project, "code-generated", "yes\n\nlooks correct")

    applied = apply_resolutions(project)
    assert len(applied) == 1
    assert applied[0].item_id == "code-generated"

    current = read_current(project, "shorten-url")
    assert current.items["code-generated"].verdict == "pass"
    # attempts_used carried over from the prior record.
    assert current.items["code-generated"].attempts_used == 2
    # Pending archived.
    assert not pp.exists()
    assert (logs_dir(project) / pp.name).exists()


def test_human_evaluation_no_resolves_to_fail(
    project, write_intent, write_current_for
):
    _intent(write_intent)
    write_current_for(
        "shorten-url",
        {"code-generated": {"verdict": "awaiting_human", "attempts_used": 0}},
        intent_version=2,
    )
    pp = _seed_human_resolved(project, "code-generated", "no")

    applied = apply_resolutions(project)
    assert len(applied) == 1

    current = read_current(project, "shorten-url")
    assert current.items["code-generated"].verdict == "fail"
    assert not pp.exists()


def test_human_evaluation_without_current_record_is_skipped(
    project, write_intent
):
    _intent(write_intent)
    # No current.yaml — the resolution has no verdict record to land on.
    pp = _seed_human_resolved(project, "code-generated", "yes")

    applied = apply_resolutions(project)
    assert applied == []
    # Left in place for the operator, never silently archived.
    assert pp.exists()
