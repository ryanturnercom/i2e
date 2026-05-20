"""Save-time validation gate for Capability intents (spec §5).

Combines:

* `validate_capability_with_config` — forced-evidence rules + effort tiers
* `installed_provider_names()` — so "unknown provider" actually fires

Designed to be called both standalone and from `intent_authoring.save`.
Error messages always include the capability slug and item id.
"""

from __future__ import annotations

from pathlib import Path

from .config import load_config
from .intent import Capability
from .provider.discovery import installed_provider_names
from .validator import ValidationError, validate_capability_with_config


def _scanned_dirs_hint(extra_paths: list[Path] | None) -> str:
    """Human-readable list of the dirs `installed_provider_names` scanned."""
    dirs = ["~/.claude/skills", "./.claude/skills"]
    if extra_paths:
        dirs.extend(str(p) for p in extra_paths)
    return ", ".join(dirs)


def _prefix_errors(cap: Capability, errors: list[str]) -> list[str]:
    """Prefix each error with `<slug> > <item id (if discoverable)>: <msg>`.

    The base validator already names the offending item id inside the message
    (e.g. ``Item 'redirect-latency-p95' has no provider...``). We pull it out
    and re-shape the line so the slug appears too.
    """
    slug = cap.frontmatter.capability
    out: list[str] = []
    for msg in errors:
        # Heuristic: pull the first quoted token after "Item" / "Constraint"
        item_id = ""
        for kw in ("Item ", "Constraint "):
            if msg.startswith(kw):
                rest = msg[len(kw):]
                if rest.startswith("'") and "'" in rest[1:]:
                    item_id = rest[1: rest.index("'", 1)]
                    break
        if item_id:
            out.append(f"{slug} > {item_id}: {msg}")
        else:
            out.append(f"{slug}: {msg}")
    return out


def gate(
    cap: Capability,
    root: Path,
    *,
    extra_skill_paths: list[Path] | None = None,
) -> None:
    """Validate ``cap`` against config + installed providers.

    Raises `ValidationError` (with slug-prefixed messages) on failure.
    """
    cfg = load_config(root)
    installed = installed_provider_names(extra_paths=extra_skill_paths)

    try:
        validate_capability_with_config(cap, cfg, installed_providers=installed)
    except ValidationError as exc:
        errors = _prefix_errors(cap, exc.errors)
        # Add discovery hint to "provider X not installed" errors so the user
        # knows where we looked.
        scanned = _scanned_dirs_hint(extra_skill_paths)
        decorated = [
            f"{e} (scanned {scanned})" if "no matching i2e-provider-" in e else e
            for e in errors
        ]
        raise ValidationError(decorated) from exc
