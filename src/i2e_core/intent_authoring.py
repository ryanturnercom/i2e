"""Deterministic helpers for the `i2e-intent` skill.

The interactive prompt-walking lives in `SKILL.md` (it's LLM-side). This
module is the deterministic core: load existing or scaffold, upsert/remove
items by id, and the save function — which runs the validation gate, bumps
``version`` when the items signature changes, and atomically writes the file.
"""

from __future__ import annotations

from pathlib import Path

from .intent import (
    Capability,
    Constraint,
    EvidenceItem,
    items_signature,
    parse_intent,
    write_intent,
)
from .intent_save_gate import gate
from .intent_template import default_capability, today_utc
from .paths import intents_dir


def intent_path(root: Path, slug: str) -> Path:
    """Return the on-disk path for a capability slug."""
    return intents_dir(Path(root)) / f"{slug}.md"


def load_or_init(root: Path, slug: str, watcher: str = "@me") -> Capability:
    """Return the parsed intent if it exists, else a fresh scaffold."""
    path = intent_path(root, slug)
    if path.exists():
        return parse_intent(path)
    return default_capability(slug, watcher)


def upsert_evidence(cap: Capability, item: EvidenceItem) -> Capability:
    """Add or replace an evidence item by ``id``. Returns a new Capability."""
    new_list = [it for it in cap.evidence if it.id != item.id]
    new_list.append(item)
    return cap.model_copy(update={"evidence": new_list})


def upsert_constraint(cap: Capability, c: Constraint) -> Capability:
    """Add or replace a constraint by ``id``. Returns a new Capability."""
    new_list = [it for it in cap.constraints if it.id != c.id]
    new_list.append(c)
    return cap.model_copy(update={"constraints": new_list})


def remove_item(cap: Capability, item_id: str) -> Capability:
    """Remove an evidence item or constraint by id. No-op if absent."""
    new_ev = [it for it in cap.evidence if it.id != item_id]
    new_cn = [it for it in cap.constraints if it.id != item_id]
    return cap.model_copy(update={"evidence": new_ev, "constraints": new_cn})


def save(
    root: Path,
    cap: Capability,
    *,
    dry_run: bool = False,
    extra_skill_paths: list[Path] | None = None,
) -> Path:
    """Validate, optionally bump version, and atomically write the intent.

    Returns the target path. Raises `ValidationError` if the gate fails;
    in that case nothing is written.

    When ``dry_run`` is True the gate still runs (so callers see any
    validation errors) but no file is written.
    """
    # 1. Validate first — refuse to write a broken intent.
    gate(cap, root, extra_skill_paths=extra_skill_paths)

    # 2. Decide whether to bump version, based on the on-disk copy (if any).
    target = intent_path(root, cap.frontmatter.capability)
    bumped = cap
    if target.exists():
        old = parse_intent(target)
        if items_signature(old) != items_signature(cap):
            new_version = old.frontmatter.version + 1
        else:
            new_version = old.frontmatter.version
        new_fm = bumped.frontmatter.model_copy(
            update={"version": new_version, "updated": today_utc()}
        )
        bumped = bumped.model_copy(update={"frontmatter": new_fm})
    else:
        # New file: keep the in-memory version (typically 1 from the template)
        # but still refresh `updated` to today.
        new_fm = bumped.frontmatter.model_copy(
            update={"updated": today_utc()}
        )
        bumped = bumped.model_copy(update={"frontmatter": new_fm})

    if dry_run:
        return target

    return write_intent(bumped, target)
