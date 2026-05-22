"""Console-driven status flip: active → draft (un-started intents only).

Symmetric with :mod:`promote`. An ``active`` intent may be sent back to
``draft`` ONLY while it has not been started — no evidence snapshot and
no in-flight worker. Once a develop+evidence cycle has run, demote is
refused so a started intent can't silently shed its run history; pulling
a started intent back is an ``i2e-intent`` job.

ONLY the ``status`` frontmatter field changes — the same narrow
boundary carve-out that backs :func:`promote`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...evidence import read_current
from ...intent import parse_intent
from ...intent_authoring import demote_intent
from ...paths import i2e_dir, intents_dir


def demote(root: Path, slug: str) -> dict[str, Any]:
    """Demote an un-started active intent back to draft.

    Returns a JSON-shaped result:
        {"valid": True,  "slug": ..., "old_status": "active", "new_status": "draft"}
        {"valid": False, "errors": [{"field": ..., "msg": ...}, ...]}
    """
    root = Path(root)
    path = intents_dir(root) / f"{slug}.md"
    if not path.exists():
        return {
            "valid": False,
            "errors": [{"field": "slug", "msg": f"intent not found: {slug}"}],
        }

    cap = parse_intent(path)
    status = cap.frontmatter.status
    if status != "active":
        return {
            "valid": False,
            "errors": [
                {
                    "field": "status",
                    "msg": f"only active intents can be demoted to draft "
                    f"(status is {status!r})",
                }
            ],
        }

    # Not-started guard 1: an evidence snapshot means a develop+evidence
    # cycle has already run against this capability.
    if read_current(root, slug) is not None:
        return {
            "valid": False,
            "errors": [
                {
                    "field": "evidence",
                    "msg": "intent has already been started — evidence exists; "
                    "demote is for un-started intents only",
                }
            ],
        }

    # Not-started guard 2: a worktree claim means a worker is in flight.
    if (i2e_dir(root) / "worktrees" / slug / "claim.json").exists():
        return {
            "valid": False,
            "errors": [
                {
                    "field": "worker",
                    "msg": "a worker is in flight on this intent; cannot demote",
                }
            ],
        }

    old, new = demote_intent(root, slug)
    return {
        "valid": True,
        "slug": slug,
        "old_status": old,
        "new_status": new,
    }
