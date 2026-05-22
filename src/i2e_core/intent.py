"""Capability intent file parser, models, and serializer."""

from __future__ import annotations

import hashlib
import os
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import frontmatter
import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .io_utils import atomic_write, dump_yaml

_KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

_EVIDENCE_HEADING = "## Evidence of success"
_CONSTRAINTS_HEADING = "## Constraints"


def _validate_kebab(v: str) -> str:
    if not isinstance(v, str) or not _KEBAB_RE.match(v):
        raise ValueError(f"id must be kebab-case (got {v!r})")
    return v


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["case", "target"]
    provider: str
    query: str
    expect: str
    window: str | None = None
    effort: str = "medium"
    # Visual-review fields. Carried through to the pending file so a human
    # reviewer sees discrete "what to open / what to do / what to compare"
    # cues instead of a wall of prose stuffed into `query`.
    url: str | None = None
    steps: list[str] | None = None
    screenshot: str | None = None

    @field_validator("id")
    @classmethod
    def _id_kebab(cls, v: str) -> str:
        return _validate_kebab(v)


class Constraint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    provider: str
    query: str
    expect: str
    effort: str = "medium"
    type: Literal["constraint"] = "constraint"
    url: str | None = None
    steps: list[str] | None = None
    screenshot: str | None = None

    @field_validator("id")
    @classmethod
    def _id_kebab(cls, v: str) -> str:
        return _validate_kebab(v)


class Frontmatter(BaseModel):
    model_config = ConfigDict(extra="allow")

    capability: str
    created: date
    updated: date
    version: int
    status: Literal["draft", "active", "shipped", "retired"]
    watcher: str = "@me"
    depends_on: list[str] = Field(default_factory=list)
    touches: list[str] = Field(default_factory=lambda: ["**"])
    spec: str | None = None
    spec_section: str | None = None
    # Orchestrator-owned mirror of the active claim. See
    # i2e_core.swarm.mirror_runtime / clear_runtime. Never written by
    # i2e-intent; only the swarm dispatcher touches it.
    runtime: dict | None = None

    @field_validator("capability")
    @classmethod
    def _cap_kebab(cls, v: str) -> str:
        return _validate_kebab(v)

    @field_validator("depends_on")
    @classmethod
    def _deps_kebab(cls, v: list[str]) -> list[str]:
        for slug in v:
            _validate_kebab(slug)
        return v

    @field_validator("touches")
    @classmethod
    def _touches_non_empty(cls, v: list[str]) -> list[str]:
        if not v:
            return ["**"]
        for g in v:
            if not isinstance(g, str) or not g.strip():
                raise ValueError(f"touches entry must be a non-empty string (got {g!r})")
        return v


class Capability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frontmatter: Frontmatter
    description: str = ""
    evidence: list[EvidenceItem] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)


# ---------- parsing ----------


def _split_body(body: str) -> tuple[str, str, str]:
    """Return (description, evidence_yaml, constraints_yaml)."""
    lines = body.splitlines()
    desc_lines: list[str] = []
    ev_lines: list[str] = []
    cn_lines: list[str] = []

    section = "desc"
    for line in lines:
        stripped = line.rstrip()
        if stripped == _EVIDENCE_HEADING:
            section = "evidence"
            continue
        if stripped == _CONSTRAINTS_HEADING:
            section = "constraints"
            continue
        if section == "desc":
            desc_lines.append(line)
        elif section == "evidence":
            ev_lines.append(line)
        else:
            cn_lines.append(line)

    description = "\n".join(desc_lines).strip("\n")
    evidence_yaml = "\n".join(ev_lines).strip("\n")
    constraints_yaml = "\n".join(cn_lines).strip("\n")
    return description, evidence_yaml, constraints_yaml


_STRING_FIELDS = {
    "id",
    "type",
    "provider",
    "query",
    "expect",
    "window",
    "effort",
    "url",
    "screenshot",
}


def _stringify(item: dict[str, Any]) -> dict[str, Any]:
    """Coerce scalar values for known string-typed fields back to strings.

    YAML 1.1 parses bare ``yes``/``no``/``on``/``off`` as booleans and numeric
    strings as ints. Capability files often use those words ("expect: yes",
    "expect: 0"). We force-convert to str for the known string fields.
    """
    out = dict(item)
    for k in _STRING_FIELDS:
        if k in out and out[k] is not None and not isinstance(out[k], str):
            v = out[k]
            if isinstance(v, bool):
                out[k] = "yes" if v else "no"
            else:
                out[k] = str(v)
    return out


def _parse_yaml_list(text: str) -> list[dict[str, Any]]:
    if not text.strip():
        return []
    data = yaml.safe_load(text)
    if data is None:
        return []
    if not isinstance(data, list):
        raise ValueError("Section must contain a YAML list of items")
    return [_stringify(it) if isinstance(it, dict) else it for it in data]


def _parse_intent_uncached(path: Path) -> Capability:
    """Parse a Capability intent file straight from disk — no caching."""
    raw = path.read_text(encoding="utf-8")
    post = frontmatter.loads(raw)
    fm = Frontmatter.model_validate(post.metadata)
    description, ev_text, cn_text = _split_body(post.content)
    ev_raw = _parse_yaml_list(ev_text)
    cn_raw = _parse_yaml_list(cn_text)
    evidence = [EvidenceItem.model_validate(it) for it in ev_raw]
    constraints = [
        Constraint.model_validate({k: v for k, v in it.items() if k != "type"})
        for it in cn_raw
    ]
    return Capability(
        frontmatter=fm,
        description=description,
        evidence=evidence,
        constraints=constraints,
    )


@lru_cache(maxsize=512)
def _parse_intent_cached(abspath: str, mtime_ns: int) -> Capability:
    """Memoised parse keyed on ``(absolute path, mtime)``.

    ``mtime_ns`` is part of the cache key only: any edit to the file rotates
    the key, so a stale parse is never returned. The cached ``Capability``
    is shared — :func:`parse_intent` deep-copies it before handing it out.
    """
    return _parse_intent_uncached(Path(abspath))


def parse_intent(path: Path) -> Capability:
    """Parse a Capability intent file into a ``Capability`` model.

    Memoised on ``(absolute path, mtime)``. A single orchestrator
    ``decide()`` re-parses each intent file 2-5 times across its branch
    walk; with the cache, every repeat is a dict lookup plus a deep copy
    instead of a fresh read + 3 YAML parses + Pydantic validation. Any edit
    rotates the mtime and forces a reparse — the same freshness contract the
    preflight cache already relies on.

    A deep copy is returned on every call, so callers that mutate the result
    (``adapt.apply_resolutions``, the intent-authoring API) cannot corrupt
    the shared cached instance.
    """
    path = Path(path)
    try:
        mtime_ns = path.stat().st_mtime_ns
    except OSError:
        # Missing/unreadable — defer to the uncached path so the real error
        # (FileNotFoundError, ...) surfaces with a clean traceback.
        return _parse_intent_uncached(path)
    cap = _parse_intent_cached(os.path.abspath(path), mtime_ns)
    return cap.model_copy(deep=True)


# ---------- serialization ----------


_EVIDENCE_KEY_ORDER = (
    "id",
    "type",
    "provider",
    "query",
    "expect",
    "window",
    "effort",
    "url",
    "steps",
    "screenshot",
)
_CONSTRAINT_KEY_ORDER = (
    "id",
    "provider",
    "query",
    "expect",
    "effort",
    "url",
    "steps",
    "screenshot",
)
_FRONTMATTER_KEY_ORDER = (
    "capability",
    "created",
    "updated",
    "version",
    "status",
    "watcher",
    "depends_on",
    "touches",
    "spec",
    "spec_section",
    "runtime",
)


def _ordered(d: dict[str, Any], order: tuple[str, ...]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k in order:
        if k in d and d[k] is not None:
            out[k] = d[k]
    for k, v in d.items():
        if k not in out and v is not None:
            out[k] = v
    return out


def _render_scalar(v: Any) -> str:
    """Render a scalar value with PyYAML, stripping doc markers."""
    # width=10**9 disables PyYAML's default 80-col wrap. _dump_item assembles
    # the surrounding `  key: ` context manually, so a wrapped continuation
    # line lands at the wrong indent and a long string fails to round-trip.
    s = yaml.safe_dump(
        v, default_flow_style=False, allow_unicode=True, width=10**9
    )
    # safe_dump appends "...\n" for top-level scalars; drop it and trailing nl.
    if s.endswith("...\n"):
        s = s[: -len("...\n")]
    return s.rstrip("\n")


def _dump_item(item: dict[str, Any]) -> str:
    """Render one YAML list item in the spec's block style."""
    lines: list[str] = []
    first = True
    for k, v in item.items():
        prefix = "- " if first else "  "
        first = False
        if isinstance(v, str) and "\n" in v:
            body = v.rstrip("\n")
            indented = "\n".join("    " + ln for ln in body.splitlines())
            lines.append(f"{prefix}{k}: |\n{indented}")
        else:
            lines.append(f"{prefix}{k}: {_render_scalar(v)}")
    return "\n".join(lines)


def serialize_intent(cap: Capability) -> str:
    """Render a Capability as canonical Markdown with YAML frontmatter."""
    fm_data = cap.frontmatter.model_dump(mode="json")
    if not fm_data.get("depends_on"):
        fm_data.pop("depends_on", None)
    # touches defaults to ["**"] (every path). Omit when the value matches
    # the default so files without an explicit touches: stay clean.
    if fm_data.get("touches") == ["**"]:
        fm_data.pop("touches", None)
    fm_data = _ordered(fm_data, _FRONTMATTER_KEY_ORDER)
    fm_yaml = yaml.safe_dump(
        fm_data, sort_keys=False, default_flow_style=False, allow_unicode=True
    ).rstrip()

    lines: list[str] = []
    lines.append("---")
    lines.append(fm_yaml)
    lines.append("---")
    lines.append("")
    if cap.description.strip():
        lines.append(cap.description.strip())
        lines.append("")
    lines.append(_EVIDENCE_HEADING)
    lines.append("")
    if cap.evidence:
        for item in cap.evidence:
            data = item.model_dump(mode="json", exclude_none=True)
            data = _ordered(data, _EVIDENCE_KEY_ORDER)
            lines.append(_dump_item(data))
            lines.append("")
    lines.append(_CONSTRAINTS_HEADING)
    lines.append("")
    if cap.constraints:
        for item in cap.constraints:
            data = item.model_dump(mode="json", exclude_none=True)
            data.pop("type", None)
            data = _ordered(data, _CONSTRAINT_KEY_ORDER)
            lines.append(_dump_item(data))
            lines.append("")
    text = "\n".join(lines).rstrip() + "\n"
    return text


def write_intent(cap: Capability, path: Path) -> Path:
    """Serialize and atomically write a Capability."""
    path = Path(path)
    atomic_write(path, serialize_intent(cap))
    return path


# ---------- signature / diff (material-change detection) ----------


# Default values that must be excluded from the signature, so they don't
# count as "material" changes. A field that matches the default doesn't
# alter the intent's behaviour.
_EVIDENCE_DEFAULTS: dict[str, Any] = {
    "window": None,
    "effort": "medium",
    "url": None,
    "steps": None,
    "screenshot": None,
}
_CONSTRAINT_DEFAULTS: dict[str, Any] = {
    "effort": "medium",
    "type": "constraint",
    "url": None,
    "steps": None,
    "screenshot": None,
}


def _evidence_canon(item: EvidenceItem) -> dict[str, Any]:
    data = item.model_dump(mode="json", exclude_none=True)
    for key, default in _EVIDENCE_DEFAULTS.items():
        if data.get(key) == default:
            data.pop(key, None)
    return {k: data[k] for k in sorted(data)}


def _constraint_canon(item: Constraint) -> dict[str, Any]:
    data = item.model_dump(mode="json", exclude_none=True)
    for key, default in _CONSTRAINT_DEFAULTS.items():
        if data.get(key) == default:
            data.pop(key, None)
    return {k: data[k] for k in sorted(data)}


def items_signature(cap: Capability) -> str:
    """SHA-256 hex of the canonical evidence + constraints lists.

    The signature is order-independent (lists are sorted by ``id``) and
    ignores default-valued fields, so cosmetic reorderings or re-stating
    a default do not change the signature.
    """
    evidence = [_evidence_canon(it) for it in cap.evidence]
    constraints = [_constraint_canon(it) for it in cap.constraints]
    evidence.sort(key=lambda d: d.get("id", ""))
    constraints.sort(key=lambda d: d.get("id", ""))
    payload = dump_yaml({"evidence": evidence, "constraints": constraints})
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def diff_summary(old: Capability, new: Capability) -> str:
    """Return a human-readable summary of what changed between ``old`` and ``new``.

    Designed for the LLM to read aloud before confirming a save.
    """
    old_ev = {it.id: it for it in old.evidence}
    new_ev = {it.id: it for it in new.evidence}
    old_cn = {it.id: it for it in old.constraints}
    new_cn = {it.id: it for it in new.constraints}

    parts: list[str] = []

    added_ev = sorted(set(new_ev) - set(old_ev))
    removed_ev = sorted(set(old_ev) - set(new_ev))
    changed_ev = sorted(
        i for i in (set(old_ev) & set(new_ev))
        if _evidence_canon(old_ev[i]) != _evidence_canon(new_ev[i])
    )

    added_cn = sorted(set(new_cn) - set(old_cn))
    removed_cn = sorted(set(old_cn) - set(new_cn))
    changed_cn = sorted(
        i for i in (set(old_cn) & set(new_cn))
        if _constraint_canon(old_cn[i]) != _constraint_canon(new_cn[i])
    )

    if added_ev:
        parts.append(f"Added evidence: {', '.join(added_ev)}.")
    if removed_ev:
        parts.append(f"Removed evidence: {', '.join(removed_ev)}.")
    if changed_ev:
        parts.append(f"Changed evidence: {', '.join(changed_ev)}.")
    if added_cn:
        parts.append(f"Added constraints: {', '.join(added_cn)}.")
    if removed_cn:
        parts.append(f"Removed constraints: {', '.join(removed_cn)}.")
    if changed_cn:
        parts.append(f"Changed constraints: {', '.join(changed_cn)}.")

    material = items_signature(old) != items_signature(new)
    if material:
        new_version = old.frontmatter.version + 1
        if new_version != new.frontmatter.version:
            new_version = new.frontmatter.version
        parts.append(
            f"Bumped version {old.frontmatter.version} -> {new_version}."
        )
    else:
        if old.description.strip() != new.description.strip():
            parts.append(
                "Description-only change; version unchanged "
                f"(stays {old.frontmatter.version})."
            )
        elif not parts:
            parts.append("No material changes.")

    return " ".join(parts)
