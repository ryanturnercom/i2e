"""Console-driven status flip: draft → active.

Narrow boundary carve-out for i2e-serve. Calls the existing
``intent_authoring`` gate so the same forced-evidence validation runs
that the ``i2e-intent`` skill applies on save. On invalid intents the
console renders a modal with the structured errors instead of writing.

ONLY the ``status`` frontmatter field changes. Body text, evidence,
constraints, watcher, depends_on, touches — none of these may be
edited through the console; they go through ``i2e-intent``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...intent import parse_intent
from ...intent_authoring import gate, set_intent_status
from ...paths import intents_dir
from ...validator import ValidationError


def promote(root: Path, slug: str) -> dict[str, Any]:
    """Promote a draft intent to active.

    Returns a JSON-shaped result:
        {"valid": True,  "slug": ..., "old_status": "draft", "new_status": "active"}
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
    if cap.frontmatter.status != "draft":
        return {
            "valid": False,
            "errors": [
                {
                    "field": "status",
                    "msg": f"cannot promote from status {cap.frontmatter.status!r}; only draft → active is exposed",
                }
            ],
        }

    try:
        gate(cap, root)
    except ValidationError as exc:
        return {
            "valid": False,
            "errors": [{"field": "evidence", "msg": e} for e in exc.errors],
        }

    set_intent_status(root, slug, "active")
    return {
        "valid": True,
        "slug": slug,
        "old_status": "draft",
        "new_status": "active",
    }
