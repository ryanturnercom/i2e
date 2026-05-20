"""Async pending-file lifecycle: awaiting_human → open re-run → resolve → archive."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from i2e_core.evidence import read_current
from i2e_core.evidence_runner import run
from i2e_core.paths import logs_dir, pending_dir
from i2e_core.pending import (
    PendingFile,
    read_pending,
    resolve_to_verdict,
    write_pending,
)
from i2e_core.provider import AsyncResult, ProviderContext

from .conftest import FakeProvider


# ---------- a tiny HumanProvider stand-in (writes a pending file) ----------


def _human_behavior(item, ctx: ProviderContext) -> AsyncResult:
    """Mimics the real i2e-provider-human: writes a pending file then returns AsyncResult."""
    now = datetime.now(timezone.utc)
    pf = PendingFile(
        kind="human_evaluation",
        capability=ctx.capability,
        item_id=item.id,
        asked_at=now,
        ask=item.query,
        expect=getattr(item, "expect", None),
        verdict_options=["yes", "no", "partial"],
    )
    path = write_pending(ctx.root, pf)
    return AsyncResult(pending=path.name)


def test_first_run_writes_pending_and_records_awaiting_human(
    project: Path, write_intent, patch_providers
):
    write_intent(
        "demo",
        evidence=[
            {
                "id": "subjective",
                "type": "case",
                "provider": "human",
                "query": "Does it feel right?",
                "expect": "yes",
            }
        ],
    )
    patch_providers({"human": FakeProvider("human", _human_behavior)})

    summary = run(project, "demo")
    assert summary.awaiting_human == 1
    assert summary.total == 1

    # Pending file is on disk.
    pdir = pending_dir(project)
    files = list(pdir.glob("*.yaml"))
    assert len(files) == 1
    pf = read_pending(files[0])
    assert pf.status == "open"
    assert pf.item_id == "subjective"

    cur = read_current(project, "demo")
    assert cur is not None
    v = cur.items["subjective"]
    assert v.verdict == "awaiting_human"
    assert v.pending == files[0].name
    assert v.attempts_used == 0  # async does NOT bump attempts


def test_rerun_while_open_keeps_awaiting_no_new_file(
    project: Path, write_intent, patch_providers
):
    write_intent(
        "demo",
        evidence=[
            {
                "id": "subjective",
                "type": "case",
                "provider": "human",
                "query": "'feel right'",
                "expect": "yes",
            }
        ],
    )
    patch_providers({"human": FakeProvider("human", _human_behavior)})

    run(project, "demo")
    pdir = pending_dir(project)
    files_before = sorted(p.name for p in pdir.glob("*.yaml"))
    assert len(files_before) == 1

    # Second run: provider will raise FileExistsError (real human provider does);
    # the runner must catch and re-emit awaiting_human with no new file.
    summary = run(project, "demo")
    files_after = sorted(p.name for p in pdir.glob("*.yaml"))
    assert files_after == files_before  # no new file

    assert summary.awaiting_human == 1
    cur = read_current(project, "demo")
    assert cur is not None
    v = cur.items["subjective"]
    assert v.verdict == "awaiting_human"
    assert v.attempts_used == 0
    assert v.pending == files_before[0]


def test_resolved_pending_translates_to_pass_and_archives(
    project: Path, write_intent, patch_providers
):
    write_intent(
        "demo",
        evidence=[
            {
                "id": "subjective",
                "type": "case",
                "provider": "human",
                "query": "'feel right'",
                "expect": "yes",
            }
        ],
    )
    patch_providers({"human": FakeProvider("human", _human_behavior)})

    # First run writes a pending file.
    run(project, "demo")
    pdir = pending_dir(project)
    pending_file = next(iter(pdir.glob("*.yaml")))

    # Human resolves it with "yes".
    pf = read_pending(pending_file)
    pf_resolved = pf.model_copy(update={"status": "resolved", "resolution": "yes"})
    from i2e_core.io_utils import atomic_write, dump_yaml

    atomic_write(pending_file, dump_yaml(pf_resolved.model_dump(mode="json")))

    # Re-run evidence: the runner should pick up the resolution, archive the
    # file, and record verdict=pass.
    summary = run(project, "demo")
    assert summary.pass_ == 1
    assert summary.awaiting_human == 0

    # Pending file moved to logs/.
    assert not pending_file.exists()
    ldir = logs_dir(project)
    archived = list(ldir.glob("*.yaml"))
    assert len(archived) == 1
    assert archived[0].name == pending_file.name

    cur = read_current(project, "demo")
    assert cur is not None
    v = cur.items["subjective"]
    assert v.verdict == "pass"


def test_resolved_no_becomes_fail(project: Path, write_intent, patch_providers):
    write_intent(
        "demo",
        evidence=[
            {
                "id": "subjective",
                "type": "case",
                "provider": "human",
                "query": "'feel right'",
                "expect": "yes",
            }
        ],
    )
    patch_providers({"human": FakeProvider("human", _human_behavior)})
    run(project, "demo")
    pdir = pending_dir(project)
    pending_file = next(iter(pdir.glob("*.yaml")))
    pf = read_pending(pending_file)
    pf_resolved = pf.model_copy(update={"status": "resolved", "resolution": "no"})
    from i2e_core.io_utils import atomic_write, dump_yaml

    atomic_write(pending_file, dump_yaml(pf_resolved.model_dump(mode="json")))

    summary = run(project, "demo")
    assert summary.fail == 1

    cur = read_current(project, "demo")
    assert cur is not None
    v = cur.items["subjective"]
    assert v.verdict == "fail"
    assert v.raw.get("resolution") == "no"


# ---------- resolve_to_verdict unit tests ----------


def test_resolve_to_verdict_yes_is_pass():
    pf = PendingFile(
        status="resolved",
        kind="human_evaluation",
        capability="x",
        item_id="i",
        ask="?",
        resolution="yes",
    )
    v = resolve_to_verdict(pf)
    assert v.verdict == "pass"
    assert v.last_observed is not None


def test_resolve_to_verdict_partial_is_fail():
    pf = PendingFile(
        status="resolved",
        kind="human_evaluation",
        capability="x",
        item_id="i",
        ask="?",
        resolution="partial",
    )
    v = resolve_to_verdict(pf)
    assert v.verdict == "fail"
    assert v.raw["resolution"] == "partial"


def test_resolve_to_verdict_open_raises():
    pf = PendingFile(
        kind="human_evaluation",
        capability="x",
        item_id="i",
        ask="?",
    )
    with pytest.raises(ValueError, match="non-resolved"):
        resolve_to_verdict(pf)


def test_resolve_to_verdict_escalation_raises():
    pf = PendingFile(
        status="resolved",
        kind="escalation",
        capability="x",
        item_id="i",
        ask="?",
        resolution="yes",
    )
    with pytest.raises(ValueError, match="human_evaluation"):
        resolve_to_verdict(pf)


def test_resolve_to_verdict_unknown_resolution_raises():
    pf = PendingFile(
        status="resolved",
        kind="human_evaluation",
        capability="x",
        item_id="i",
        ask="?",
        resolution="maybe",
    )
    with pytest.raises(ValueError, match="Unrecognised"):
        resolve_to_verdict(pf)
