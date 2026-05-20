"""Deterministic helpers for the ``i2e-spec`` skill.

A PRD or design doc decomposes into N capability intents — one per H2
section. The LLM-side skill takes a markdown document and asks the human
to confirm the decomposition before any intent flips to active. This
module is the deterministic core:

* :func:`decompose` — markdown text -> list of stub ``Capability`` models.
* :func:`save_decomposition` — write ``.i2e/specs/<slug>.md`` plus the
  decomposed draft intents under ``.i2e/intents/``.
* :func:`reconcile` — re-decompose a (possibly edited) spec on disk and
  diff against existing intents; return a list of proposed actions.

The decomposer is intentionally conservative. It emits stub evidence (a
single pytest case per capability) so the file validates against the
forced-evidence rules even before a human fleshes it out. Real cases come
in via ``i2e-intent``.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .intent import (
    Capability,
    EvidenceItem,
    Frontmatter,
    parse_intent,
    write_intent,
)
from .io_utils import atomic_write
from .paths import intents_dir, specs_dir

_H2_RE = re.compile(r"^##\s+(?:Section\s+\d+\s*[:\-]\s*)?(.+?)\s*$")
_SLUG_NON = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    """Return a kebab-case slug for a section title.

    Drops any leading "Section N:" prefix, lower-cases, collapses non-alnum
    runs to single hyphens, strips leading/trailing hyphens.
    """
    s = _SLUG_NON.sub("-", title.strip().lower()).strip("-")
    return s


def _parse_sections(prd: str) -> list[tuple[str, str, str]]:
    """Walk a markdown PRD and return ``(section_ref, title, body)``.

    Only H2 (``##``) headings start a section. ``section_ref`` is the
    1-based index (as a string) so it composes cleanly with the
    ``spec_section:`` frontmatter field.
    """
    lines = prd.splitlines()
    sections: list[tuple[str, str, str]] = []
    title: str | None = None
    ref: str | None = None
    body: list[str] = []
    for line in lines:
        m = _H2_RE.match(line)
        if m:
            if title is not None and ref is not None:
                sections.append((ref, title, "\n".join(body).strip()))
            title = m.group(1).strip()
            ref = str(len(sections) + 1)
            body = []
        elif title is not None:
            body.append(line)
    if title is not None and ref is not None:
        sections.append((ref, title, "\n".join(body).strip()))
    return sections


def _stub_evidence(slug: str) -> list[EvidenceItem]:
    """One pytest case per capability so it validates immediately.

    The real cases are written by ``i2e-intent`` (or by hand) after the
    decomposition is reviewed.
    """
    underscore = slug.replace("-", "_")
    return [
        EvidenceItem(
            id=f"{slug}-implemented",
            type="case",
            provider="pytest",
            query=f"tests/test_{underscore}.py::test_implemented",
            expect="passes",
            effort="medium",
        )
    ]


def _default_touches(slug: str) -> list[str]:
    """Guess a sensible ``touches:`` for a freshly-decomposed capability.

    Convention: ``src/<slug>/**`` plus the test file for the stub case.
    The human is expected to refine this when activating the intent.
    """
    underscore = slug.replace("-", "_")
    return [f"src/{underscore}/**", f"tests/test_{underscore}.py"]


def decompose(prd: str, *, slug: str) -> list[Capability]:
    """Walk H2 headings in ``prd`` and build one stub Capability per section.

    Every output Capability is ``status: draft`` and carries
    ``spec: <slug>`` plus ``spec_section: <ref>`` so :func:`reconcile`
    can find its peers later. ``depends_on:`` is populated from spec
    order — each section depends on the previous capability, so the
    orchestrator will walk them front-to-back.
    """
    today = date.today()
    sections = _parse_sections(prd)
    caps: list[Capability] = []
    prev_slug: str | None = None
    for ref, title, body in sections:
        cap_slug = slugify(title)
        if not cap_slug:
            continue
        fm = Frontmatter(
            capability=cap_slug,
            created=today,
            updated=today,
            version=1,
            status="draft",
            watcher="@me",
            depends_on=[prev_slug] if prev_slug else [],
            touches=_default_touches(cap_slug),
            spec=slug,
            spec_section=ref,
        )
        description = body or f"From {slug} section {ref}: {title}."
        cap = Capability(
            frontmatter=fm,
            description=description,
            evidence=_stub_evidence(cap_slug),
            constraints=[],
        )
        caps.append(cap)
        prev_slug = cap_slug
    return caps


def save_decomposition(
    root: Path, prd: str, *, slug: str
) -> list[Path]:
    """Persist a PRD and its decomposed draft intents.

    Returns the list of paths written: the preserved spec file first,
    followed by each intent in spec order. Existing intent files with
    the same slug are overwritten — the caller is expected to run
    :func:`reconcile` first if they care about prior edits.
    """
    root = Path(root)
    written: list[Path] = []

    spec_path = specs_dir(root) / f"{slug}.md"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(spec_path, prd)
    written.append(spec_path)

    base = intents_dir(root)
    base.mkdir(parents=True, exist_ok=True)
    for cap in decompose(prd, slug=slug):
        path = base / f"{cap.frontmatter.capability}.md"
        write_intent(cap, path)
        written.append(path)
    return written


# ---------- reconciliation ----------


class ReconcileAction(BaseModel):
    """One proposed change emitted by :func:`reconcile`.

    The ``i2e-spec --reconcile`` workflow turns these into pending files so
    the human can accept or reject each change before any active intent
    moves.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["add", "edit", "retire"]
    capability: str
    spec_section: str | None = None
    reason: str = ""


def _intents_for_spec(root: Path, slug: str) -> dict[str, Capability]:
    base = intents_dir(Path(root))
    out: dict[str, Capability] = {}
    if not base.exists():
        return out
    for p in sorted(base.glob("*.md")):
        try:
            cap = parse_intent(p)
        except Exception:
            continue
        if cap.frontmatter.spec == slug:
            out[cap.frontmatter.capability] = cap
    return out


def reconcile(root: Path, slug: str) -> list[ReconcileAction]:
    """Diff the on-disk spec against the intents that claim it.

    Algorithm: re-decompose the spec, compare the resulting capability
    set against the intents whose frontmatter has ``spec: <slug>``, and
    emit one :class:`ReconcileAction` per difference.

    Add / retire are set-difference. Edit fires when both sides have the
    capability but the section's body text has drifted — the description
    is the only deterministic signal of "the spec changed under us."
    Returns an empty list if the spec file is missing.
    """
    root = Path(root)
    spec_path = specs_dir(root) / f"{slug}.md"
    if not spec_path.exists():
        return []
    prd = spec_path.read_text(encoding="utf-8")
    new_caps = {c.frontmatter.capability: c for c in decompose(prd, slug=slug)}
    current = _intents_for_spec(root, slug)

    actions: list[ReconcileAction] = []
    new_keys = set(new_caps)
    cur_keys = set(current)

    for s in sorted(new_keys - cur_keys):
        actions.append(
            ReconcileAction(
                kind="add",
                capability=s,
                spec_section=new_caps[s].frontmatter.spec_section,
                reason="new section in spec",
            )
        )
    for s in sorted(cur_keys - new_keys):
        actions.append(
            ReconcileAction(
                kind="retire",
                capability=s,
                spec_section=current[s].frontmatter.spec_section,
                reason="section removed from spec",
            )
        )
    for s in sorted(cur_keys & new_keys):
        if current[s].description.strip() != new_caps[s].description.strip():
            actions.append(
                ReconcileAction(
                    kind="edit",
                    capability=s,
                    spec_section=new_caps[s].frontmatter.spec_section,
                    reason="section body changed",
                )
            )
    return actions


__all__ = [
    "ReconcileAction",
    "decompose",
    "reconcile",
    "save_decomposition",
    "slugify",
]
