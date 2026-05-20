"""Deterministic helpers for the `i2e-develop` skill.

The actual code-writing is LLM-side; this module is the deterministic core:

* :func:`diff_against_current` — what changed since the last evidence run
* :func:`suggested_src_paths` / :func:`suggested_test_paths` — convention defaults
* :func:`develop_summary` — single-line log entry for `.i2e/logs/<tick>.yaml`
* :func:`needs_develop` / :func:`scoped_capabilities` — idempotency
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .evidence import read_current
from .intent import Capability, Constraint, EvidenceItem, parse_intent
from .paths import intents_dir

# The verdicts that mean "this item did not prove out last time". The LLM
# reads `DevelopDiff.last_failures` to know which items to focus on first.
_FAILURE_VERDICTS = {"fail", "unmet", "trending"}


class DevelopDiff(BaseModel):
    """What the develop step needs to know about the capability's state.

    ``new_items``, ``changed_items``, ``removed_items`` are inferred by
    comparing the current intent's items (evidence + constraints) against the
    items that the last evidence run recorded in ``current.yaml``. We don't
    store historical intents, so this is the only deterministic signal we
    have. ``last_failures`` carries the most recent failure reason per item.
    """

    model_config = ConfigDict(extra="forbid")

    prior_version: int | None = None
    current_version: int
    new_items: list[str] = Field(default_factory=list)
    changed_items: list[str] = Field(default_factory=list)
    removed_items: list[str] = Field(default_factory=list)
    # (item_id, reason) pairs, where reason is raw.error or raw.output.
    last_failures: list[tuple[str, str]] = Field(default_factory=list)


def _all_item_ids(cap: Capability) -> list[str]:
    return [it.id for it in cap.evidence] + [it.id for it in cap.constraints]


def _failure_reason(raw: dict) -> str:
    """Best-effort string explaining why an item failed.

    Prefers ``raw.error`` (provider-reported error) then ``raw.output``
    (captured stdout/stderr). Falls back to empty string. Never raises.
    """
    if not raw:
        return ""
    err = raw.get("error")
    if isinstance(err, str) and err.strip():
        return err
    out = raw.get("output")
    if isinstance(out, str) and out.strip():
        return out
    return ""


def diff_against_current(root: Path, capability: str) -> DevelopDiff:
    """Compute new/changed/removed item ids and last-failure reasons.

    Reads the capability's intent file (required) and its ``current.yaml``
    (optional). The latter is the only durable record of which items the
    system has already accounted for, since intents are not snapshotted on
    disk.
    """
    root = Path(root)
    intent_path = intents_dir(root) / f"{capability}.md"
    cap = parse_intent(intent_path)
    current = read_current(root, capability)
    current_ids = list(current.items.keys()) if current else []
    intent_ids = _all_item_ids(cap)

    prior_version = current.intent_version if current else None
    current_set = set(current_ids)
    intent_set = set(intent_ids)

    new_items = sorted(intent_set - current_set)
    removed_items = sorted(current_set - intent_set)

    # An item is "changed" if it existed in both and the intent's version has
    # advanced since the recorded run. We can't compare item bodies (the prior
    # intent isn't stored), so versioning is our best deterministic signal:
    # when the intent has bumped, every still-present item is potentially
    # touched. If the version is unchanged, nothing is considered changed.
    changed_items: list[str] = []
    if (
        prior_version is not None
        and prior_version < cap.frontmatter.version
    ):
        changed_items = sorted(intent_set & current_set)

    last_failures: list[tuple[str, str]] = []
    if current is not None:
        for item_id, verdict in current.items.items():
            if verdict.verdict in _FAILURE_VERDICTS:
                last_failures.append((item_id, _failure_reason(verdict.raw)))
        last_failures.sort(key=lambda t: t[0])

    return DevelopDiff(
        prior_version=prior_version,
        current_version=cap.frontmatter.version,
        new_items=new_items,
        changed_items=changed_items,
        removed_items=removed_items,
        last_failures=last_failures,
    )


def suggested_src_paths(cap: Capability) -> list[Path]:
    """Default ``src/`` path for a capability.

    Convention: a capability ``shorten-url`` ⇒ ``src/shorten_url/__init__.py``.
    The LLM is free to override when the codebase clearly wants something else
    (e.g. an existing package layout); this is just the default seed.
    """
    slug = cap.frontmatter.capability
    pkg = slug.replace("-", "_")
    return [Path(f"src/{pkg}/__init__.py")]


def suggested_test_paths(item: EvidenceItem | Constraint) -> Path | None:
    """Default test path for an evidence item or constraint.

    For the ``pytest`` provider, parses a nodeid of the form
    ``tests/foo.py::test_bar`` and returns ``Path("tests/foo.py")``. For any
    other provider (datadog, sentry, human, ...) returns ``None`` — there's
    no general convention there, and we'd rather say "I don't know" than
    invent one.
    """
    if item.provider != "pytest":
        return None
    query = (item.query or "").strip()
    if not query:
        return None
    # Strip a ``::test_xxx`` suffix if present; otherwise treat the whole
    # query as the file path.
    file_part = query.split("::", 1)[0].strip()
    if not file_part:
        return None
    return Path(file_part)


def develop_summary(diff: DevelopDiff, files_touched: list[Path]) -> str:
    """Single-line log entry for the tick log.

    Includes the version transition, item-diff counts, and the touched file
    count. Kept single-line so it slots cleanly into a YAML scalar inside
    ``.i2e/logs/<tick>.yaml``.
    """
    if diff.prior_version is None:
        version_str = f"intent v{diff.current_version} (first develop)"
    elif diff.prior_version == diff.current_version:
        version_str = f"intent v{diff.current_version} (no version bump)"
    else:
        version_str = (
            f"intent v{diff.prior_version} -> v{diff.current_version}"
        )
    return (
        f"develop: {version_str}; "
        f"new={len(diff.new_items)} "
        f"changed={len(diff.changed_items)} "
        f"removed={len(diff.removed_items)}; "
        f"files_touched={len(files_touched)}"
    )


# ---------- idempotency ----------


def needs_develop(root: Path, capability: str) -> bool:
    """Return True iff develop has work to do for ``capability``.

    True when no ``current.yaml`` exists, OR when the recorded
    ``intent_version`` is older than the capability's frontmatter version.
    False when versions match.
    """
    root = Path(root)
    intent_path = intents_dir(root) / f"{capability}.md"
    cap = parse_intent(intent_path)
    current = read_current(root, capability)
    if current is None:
        return True
    return current.intent_version < cap.frontmatter.version


def scoped_capabilities(root: Path) -> list[Capability]:
    """Return all active capabilities that need develop.

    Walks ``.i2e/intents/*.md``, filters to ``status == "active"``, and
    returns only those for which :func:`needs_develop` is True. Sorted by
    capability slug for deterministic ordering.
    """
    root = Path(root)
    base = intents_dir(root)
    if not base.exists():
        return []
    out: list[Capability] = []
    for path in sorted(base.glob("*.md")):
        cap = parse_intent(path)
        if cap.frontmatter.status != "active":
            continue
        if needs_develop(root, cap.frontmatter.capability):
            out.append(cap)
    return out
