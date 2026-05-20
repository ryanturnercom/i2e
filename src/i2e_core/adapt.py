"""Deterministic helpers for the ``i2e-adapt`` skill.

The loop's brain. Three entry points:

- :func:`plan` — inspect ``current.yaml`` for a capability and bucket every
  non-passing item into ``retries`` (budget remaining) vs ``escalations``
  (budget exhausted).
- :func:`escalate` — write a ``kind: escalation`` pending file for one item
  with the 3-most-recent attempts and a 4-option ``ask:`` block.
- :func:`apply_resolutions` — translate every ``status: resolved`` pending
  file in ``.i2e/pending/`` back into an intent edit (or ``current.yaml``
  edit), then archive the pending file into ``.i2e/logs/``.

**Intent-file carve-out:** ``i2e-intent`` is normally the only skill that
writes to ``.i2e/intents/``. :func:`apply_resolutions` is the single, gated
exception — see its docstring.
"""

from __future__ import annotations

import re
from datetime import date as _date
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field

from .config import I2EConfig, load_config, resolve_max_attempts
from .evidence import (
    CurrentEvidence,
    ItemVerdict,
    list_runs,
    read_current,
    read_run,
    write_current,
)
from .intent import (
    Capability,
    Constraint,
    EvidenceItem,
    parse_intent,
    write_intent,
)
from .paths import intents_dir, pending_dir
from .pending import (
    PendingFile,
    archive_pending,
    list_open_pending,
    list_resolved_pending,
    pending_filename,
    read_pending,
    write_pending,
)
from .tick_log import changes_since


# Verdicts that mean "we are not done with this item yet" — adapt's input.
_OPEN_VERDICTS = frozenset({"fail", "unmet", "trending"})
# Verdicts that mean "this item is settled for now" — no adapt work needed.
_DONE_VERDICTS = frozenset({"pass", "met", "awaiting_human"})


# ---------- public dataclasses ----------


class ItemBudget(BaseModel):
    """One non-passing item's budget snapshot."""

    model_config = ConfigDict(extra="forbid")

    item_id: str
    effort: str
    attempts_used: int
    max_attempts: int
    verdict: str


class AdaptPlan(BaseModel):
    """The output of :func:`plan` for one capability tick."""

    model_config = ConfigDict(extra="forbid")

    capability: str
    retries: list[ItemBudget] = Field(default_factory=list)
    escalations: list[ItemBudget] = Field(default_factory=list)
    done: list[str] = Field(default_factory=list)


class ResolutionApplied(BaseModel):
    """One resolved pending file successfully applied."""

    model_config = ConfigDict(extra="forbid")

    pending_path: Path
    capability: str
    item_id: str
    choice: int
    intent_changed: bool


# ---------- helpers ----------


def _intent_path(root: Path, capability: str) -> Path:
    return intents_dir(Path(root)) / f"{capability}.md"


def _item_type_for(cap: Capability, item_id: str) -> Literal["case", "target", "constraint"]:
    """Look up an item's type by id (case/target/constraint)."""
    for ev in cap.evidence:
        if ev.id == item_id:
            return ev.type  # type: ignore[return-value]
    for cn in cap.constraints:
        if cn.id == item_id:
            return "constraint"
    raise KeyError(
        f"item {item_id!r} not found in capability {cap.frontmatter.capability!r}"
    )


def _item_effort(cap: Capability, item_id: str) -> str:
    for ev in cap.evidence:
        if ev.id == item_id:
            return ev.effort
    for cn in cap.constraints:
        if cn.id == item_id:
            return cn.effort
    raise KeyError(item_id)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------- has_open_escalation ----------


def has_open_escalation(root: Path, capability: str, item_id: str) -> bool:
    """True iff an open pending file exists for ``(capability, item_id)``.

    Any ``kind`` counts (we don't want to double-escalate even if an
    ``human_evaluation`` pending happens to be open for the same item).
    """
    for p in list_open_pending(Path(root)):
        try:
            pf = read_pending(p)
        except Exception:
            continue
        if pf.capability == capability and pf.item_id == item_id:
            return True
    return False


# ---------- plan ----------


def plan(root: Path, capability: str) -> AdaptPlan:
    """Bucket every non-passing item into ``retries`` vs ``escalations``.

    Items in ``pass``/``met``/``awaiting_human`` go into ``done`` (we do not
    spend budget on them). Items with an open pending file (any kind) are
    also placed into ``done`` — they are already in the human's queue, so
    adapt should not propose another retry or generate a duplicate
    escalation file.
    """
    root = Path(root)
    cap = parse_intent(_intent_path(root, capability))
    current = read_current(root, capability)
    cfg = load_config(root)

    pl = AdaptPlan(capability=capability)
    if current is None:
        return pl

    for item_id, verdict in current.items.items():
        if verdict.verdict in _DONE_VERDICTS:
            pl.done.append(item_id)
            continue
        if verdict.verdict not in _OPEN_VERDICTS:
            # Future-proofing: any unknown verdict is left alone.
            pl.done.append(item_id)
            continue
        if has_open_escalation(root, capability, item_id):
            # Already in the human's queue; not actionable by adapt.
            pl.done.append(item_id)
            continue

        try:
            item_type = _item_type_for(cap, item_id)
            effort = _item_effort(cap, item_id)
        except KeyError:
            # The item exists in current.yaml but not in the intent
            # (e.g. retired after the last run). Skip it; the orchestrator's
            # next reconcile pass will clean current.yaml up.
            pl.done.append(item_id)
            continue

        max_attempts = resolve_max_attempts(cfg, item_type, effort)
        budget = ItemBudget(
            item_id=item_id,
            effort=effort,
            attempts_used=verdict.attempts_used,
            max_attempts=max_attempts,
            verdict=verdict.verdict,
        )
        if verdict.attempts_used < max_attempts:
            pl.retries.append(budget)
        else:
            pl.escalations.append(budget)

    pl.retries.sort(key=lambda b: b.item_id)
    pl.escalations.sort(key=lambda b: b.item_id)
    pl.done.sort()
    return pl


# ---------- escalate ----------


_ASK_TEMPLATE = (
    "Three improvement loops tried — {observed_summary}.\n"
    "Pick one:\n"
    "  1. Loosen the target (e.g. \"{example}\")\n"
    "  2. Try a new approach (describe)\n"
    "  3. Retire this target (no longer the right measure)\n"
    "  4. Accept current state as \"met\" and continue\n"
)


def _observed_summary(verdict: ItemVerdict) -> str:
    """Single-line "what we saw" for the ask: prelude."""
    if verdict.value:
        return f"observed {verdict.value!r} (verdict {verdict.verdict})"
    return f"verdict was {verdict.verdict}"


def _loosen_example(item_expect: str) -> str:
    """A toy "loosen" example to drop into the ask: block.

    The human will fill in the real value; this is only a hint of the shape.
    Kept deliberately minimal.
    """
    expect = (item_expect or "").strip()
    return f"loosen {expect}" if expect else "loosen the threshold"


def _build_attempts(
    root: Path,
    capability: str,
    item_id: str,
    current: CurrentEvidence,
) -> list[dict]:
    """Build the ``attempts`` block: last 3 (run_id, changed, observed)."""
    # Most recent run snapshots, newest first, capped at 3.
    run_paths = list_runs(root, capability)
    recent_paths = list(reversed(run_paths))[:3]

    # Lookup table for "what changed" descriptions per tick.
    change_map: dict[str, str] = {
        tick_id: desc
        for tick_id, desc in changes_since(root, capability, item_id, n=3)
    }

    attempts: list[dict] = []
    for rp in recent_paths:
        try:
            snap = read_run(rp)
        except Exception:
            continue
        item_verdict = snap.items.get(item_id)
        observed = (
            item_verdict.value
            if item_verdict and item_verdict.value
            else (item_verdict.verdict if item_verdict else "(no record)")
        )
        attempts.append(
            {
                "run_id": snap.run_id,
                "changed": change_map.get(snap.run_id, "(no tick log)"),
                "observed": observed,
            }
        )

    # If we found no run snapshots at all but current.yaml says attempts_used>0,
    # emit a placeholder so the human sees something useful.
    if not attempts:
        verdict = current.items.get(item_id)
        observed = (verdict.value if verdict and verdict.value else
                    (verdict.verdict if verdict else "(no record)"))
        attempts.append(
            {
                "run_id": current.last_run,
                "changed": "(no tick log)",
                "observed": observed,
            }
        )
    return attempts


def escalate(root: Path, capability: str, item_id: str) -> Path:
    """Write a ``kind: escalation`` pending file for one item.

    Raises ``FileExistsError`` if an open pending file for the same item
    already exists (``write_pending`` enforces this atomically).
    """
    root = Path(root)
    cap = parse_intent(_intent_path(root, capability))
    current = read_current(root, capability)
    if current is None:
        raise FileNotFoundError(
            f"No current.yaml for capability {capability!r} — cannot escalate."
        )
    verdict = current.items.get(item_id)
    if verdict is None:
        raise KeyError(
            f"item {item_id!r} not present in current.yaml for {capability!r}"
        )

    # Resolve item type + budget for the reason line.
    item_type = _item_type_for(cap, item_id)
    effort = _item_effort(cap, item_id)
    cfg = load_config(root)
    max_attempts = resolve_max_attempts(cfg, item_type, effort)
    attempts_used = verdict.attempts_used

    # Look up the original "expect" so the loosen-example reads sensibly.
    intent_expect: str = ""
    for ev in cap.evidence:
        if ev.id == item_id:
            intent_expect = ev.expect
            break
    else:
        for cn in cap.constraints:
            if cn.id == item_id:
                intent_expect = cn.expect
                break

    attempts = _build_attempts(root, capability, item_id, current)

    ask = _ASK_TEMPLATE.format(
        observed_summary=_observed_summary(verdict),
        example=_loosen_example(intent_expect),
    )

    pf = PendingFile(
        status="open",
        kind="escalation",
        capability=capability,
        item_id=item_id,
        escalated_at=_now_utc(),
        reason=(
            f"max_attempts exhausted ({attempts_used}/{max_attempts}) "
            f"without meeting threshold"
        ),
        expect=intent_expect or None,
        observed=verdict.value or None,
        attempts=attempts,
        ask=ask,
    )
    return write_pending(root, pf)


# ---------- apply_resolutions ----------


# Resolution-parsing forms accepted by :func:`apply_resolutions`:
#
#   1, 1., 1), option 1, loosen     →  choice 1 (loosen the target)
#   2, 2., 2), option 2, new        →  choice 2 (try a new approach)
#   3, 3., 3), option 3, retire     →  choice 3 (retire the item)
#   4, 4., 4), option 4, accept     →  choice 4 (accept current state)
#
# The first matching token wins. Match is case-insensitive and looks at the
# first non-empty line of the resolution.
_KEYWORD_TO_CHOICE: dict[str, int] = {
    "loosen": 1,
    "new": 2,
    "approach": 2,
    "retire": 3,
    "accept": 4,
}
_NUMERIC_RE = re.compile(r"^\s*(?:option\s+)?([1-4])\s*[\.\):]?", re.IGNORECASE)

_NEW_EXPECT_RE = re.compile(
    r"^\s*new\s+expect\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE
)


def _parse_choice(resolution: str) -> int:
    """Return 1-4, or raise ValueError if unparseable."""
    if resolution is None:
        raise ValueError("resolution is missing")
    text = resolution.strip()
    if not text:
        raise ValueError("resolution is empty")
    # Try numeric first on the first line.
    first_line = text.splitlines()[0].strip()
    m = _NUMERIC_RE.match(first_line)
    if m:
        return int(m.group(1))
    # Try keyword on the whole resolution.
    lowered = text.lower()
    for kw, choice in _KEYWORD_TO_CHOICE.items():
        # Whole-word match so e.g. "newer" doesn't match "new".
        if re.search(rf"(?<![A-Za-z]){re.escape(kw)}(?![A-Za-z])", lowered):
            return choice
    raise ValueError(
        f"could not parse resolution choice from {resolution!r}; "
        "expected 1-4, '1)', 'option 1', or one of "
        "loosen/new/retire/accept"
    )


def _parse_new_expect(resolution: str) -> str | None:
    """Extract a ``new expect: <value>`` line from a resolution body."""
    if not resolution:
        return None
    m = _NEW_EXPECT_RE.search(resolution)
    if m:
        return m.group(1).strip().strip('"\'')
    return None


def _apply_loosen(
    root: Path, cap: Capability, item_id: str, resolution: str
) -> bool:
    """Choice 1: update ``EvidenceItem.expect`` (or ``Constraint.expect``).

    Requires a ``new expect: <value>`` line in the resolution body. Raises
    ``ValueError`` otherwise — we refuse to silently leave the intent
    unchanged.
    """
    new_expect = _parse_new_expect(resolution)
    if not new_expect:
        raise ValueError(
            f"resolution for {cap.frontmatter.capability}/{item_id}: "
            "option 1 (loosen) requires a 'new expect: <value>' line"
        )
    changed = False
    for ev in cap.evidence:
        if ev.id == item_id:
            ev.expect = new_expect
            changed = True
            break
    else:
        for cn in cap.constraints:
            if cn.id == item_id:
                cn.expect = new_expect
                changed = True
                break
    if not changed:
        raise KeyError(
            f"item {item_id!r} not found in capability "
            f"{cap.frontmatter.capability!r}"
        )
    cap.frontmatter.version += 1
    cap.frontmatter.updated = _date.today()
    return True


def _apply_new_approach(
    root: Path, capability: str, item_id: str, resolution: str
) -> bool:
    """Choice 2: reset ``attempts_used`` to 0 in current.yaml.

    Returns False — the intent is NOT modified for choice 2. The approach
    text is appended into ``current.yaml`` as ``raw.new_approach`` so the
    next develop pass can read it; the orchestrator's tick log will also
    record a ``new_approach: ...`` action.
    """
    current = read_current(root, capability)
    if current is None:
        raise FileNotFoundError(
            f"No current.yaml for {capability!r}; cannot apply new approach."
        )
    verdict = current.items.get(item_id)
    if verdict is None:
        raise KeyError(f"item {item_id!r} not in current.yaml")
    verdict.attempts_used = 0
    # Carry the approach text forward for the next develop pass.
    approach_text = (resolution or "").strip()
    if approach_text:
        verdict.raw = {**(verdict.raw or {}), "new_approach": approach_text}
    write_current(root, current)
    return False


def _apply_retire(cap: Capability, item_id: str) -> bool:
    """Choice 3: remove the item from the capability; bump version."""
    before_ev = len(cap.evidence)
    cap.evidence = [it for it in cap.evidence if it.id != item_id]
    before_cn = len(cap.constraints)
    cap.constraints = [it for it in cap.constraints if it.id != item_id]
    if len(cap.evidence) == before_ev and len(cap.constraints) == before_cn:
        raise KeyError(
            f"item {item_id!r} not found in capability "
            f"{cap.frontmatter.capability!r}"
        )
    cap.frontmatter.version += 1
    cap.frontmatter.updated = _date.today()
    return True


def _apply_accept(
    root: Path, capability: str, item_id: str, cap: Capability
) -> bool:
    """Choice 4: set verdict to ``pass`` (case/constraint) or ``met`` (target).

    Intent is untouched.
    """
    current = read_current(root, capability)
    if current is None:
        raise FileNotFoundError(
            f"No current.yaml for {capability!r}; cannot apply accept."
        )
    verdict = current.items.get(item_id)
    if verdict is None:
        raise KeyError(f"item {item_id!r} not in current.yaml")

    # Determine new verdict from item type.
    try:
        item_type = _item_type_for(cap, item_id)
    except KeyError:
        item_type = "case"  # safe default — case verdicts are pass/fail
    new_verdict = "met" if item_type == "target" else "pass"
    current.items[item_id] = ItemVerdict(
        verdict=new_verdict,
        value=verdict.value,
        attempts_used=verdict.attempts_used,
        last_observed=_now_utc(),
        raw={**(verdict.raw or {}), "accepted": True},
    )
    write_current(root, current)
    return False


def apply_resolutions(root: Path) -> list[ResolutionApplied]:
    """Translate every resolved pending file into an intent or current.yaml edit.

    Iterates :func:`i2e_core.pending.list_resolved_pending`. For each file,
    parses the ``resolution:`` field into one of four choices and applies
    the right edit:

    - **1 — loosen**: parses a ``new expect: <value>`` line from the
      resolution body, updates ``EvidenceItem.expect`` (or
      ``Constraint.expect``), bumps ``frontmatter.version`` and updates
      ``frontmatter.updated``. Raises ``ValueError`` if no new value is
      present — we refuse silent intent edits.
    - **2 — new approach**: resets ``attempts_used`` to 0 for the item in
      ``current.yaml``; carries the approach text forward via
      ``raw.new_approach``. The intent is NOT modified.
    - **3 — retire**: removes the item from ``cap.evidence`` or
      ``cap.constraints``; bumps ``frontmatter.version``.
    - **4 — accept**: in ``current.yaml`` only, sets the verdict to ``met``
      (target) or ``pass`` (case/constraint). The intent is NOT modified.

    After each successful apply, archives the pending file to
    ``.i2e/logs/``. Errors on individual files are logged-and-skipped
    (best-effort batch); the function never raises after the first failure.

    **Resolution parser accepts many shapes** (case-insensitive):
    ``"1"``, ``"1."``, ``"1)"``, ``"option 1"``, ``"loosen"``,
    ``"2 — try X"``, ``"new"``, ``"approach"``, ``"3"``, ``"retire"``,
    ``"4"``, ``"accept"``.

    **Intent carve-out:** This is the ONE place outside ``i2e-intent`` that
    may modify ``.i2e/intents/*.md``. It uses
    :func:`i2e_core.intent.write_intent` so writes are atomic. The
    orchestrator's preflight (branch 1) is the only caller.
    """
    root = Path(root)
    applied: list[ResolutionApplied] = []
    for pp in list_resolved_pending(root):
        try:
            pf = read_pending(pp)
        except Exception:
            # Malformed pending file — leave it alone; operator can clean up.
            continue
        try:
            choice = _parse_choice(pf.resolution or "")
            cap_path = _intent_path(root, pf.capability)
            cap = parse_intent(cap_path)
            intent_changed = False
            if choice == 1:
                intent_changed = _apply_loosen(
                    root, cap, pf.item_id, pf.resolution or ""
                )
                write_intent(cap, cap_path)
            elif choice == 2:
                intent_changed = _apply_new_approach(
                    root, pf.capability, pf.item_id, pf.resolution or ""
                )
            elif choice == 3:
                intent_changed = _apply_retire(cap, pf.item_id)
                write_intent(cap, cap_path)
            elif choice == 4:
                intent_changed = _apply_accept(
                    root, pf.capability, pf.item_id, cap
                )
            else:  # pragma: no cover — _parse_choice raises before this branch
                raise ValueError(f"unknown choice {choice}")

            archived = archive_pending(root, pp)
            applied.append(
                ResolutionApplied(
                    pending_path=archived,
                    capability=pf.capability,
                    item_id=pf.item_id,
                    choice=choice,
                    intent_changed=intent_changed,
                )
            )
        except Exception:
            # Best-effort batch — log-and-skip. The pending file stays put
            # so the operator can inspect it.
            continue
    return applied


__all__ = [
    "AdaptPlan",
    "ItemBudget",
    "ResolutionApplied",
    "apply_resolutions",
    "escalate",
    "has_open_escalation",
    "plan",
]
