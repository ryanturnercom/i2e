"""Standing reference loader for `.i2e/context/`.

`.i2e/context/` holds standing reference documents (ARCHITECTURE.md, DESIGN.md,
glossary, conventions) — see spec §3. They're read by `i2e-develop` but never
proven; they ground the AI's choices without being evidence themselves.

This module only does deterministic IO: listing files, loading them under a
character budget, and producing a one-line-per-file index. The actual use of
that material is LLM-side.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .paths import context_dir

_log = logging.getLogger(__name__)

# Default global character budget for loaded context bodies. The orchestrator
# may override; this default keeps the prompt bounded.
_DEFAULT_MAX_CHARS = 80_000


def list_context_files(root: Path) -> list[Path]:
    """Return all ``*.md`` files under ``.i2e/context/`` (recursive).

    Paths are returned as absolute paths sorted by their path string for
    deterministic ordering (so retries see the same order). Returns an empty
    list when the directory is missing or empty — never raises.
    """
    base = context_dir(Path(root))
    if not base.exists():
        return []
    files = [p for p in base.rglob("*.md") if p.is_file()]
    files.sort(key=lambda p: str(p))
    return files


def _relative(root: Path, p: Path) -> str:
    """Return ``p`` relative to ``.i2e/context/`` as a forward-slash string."""
    base = context_dir(Path(root))
    try:
        rel = p.relative_to(base)
    except ValueError:
        rel = p
    return rel.as_posix()


def load_context(
    root: Path,
    max_chars: int = _DEFAULT_MAX_CHARS,
) -> dict[str, str]:
    """Load every context file's text, bounded by a global character budget.

    Returns ``{relative_path: content}`` in the same deterministic order as
    :func:`list_context_files`. The total length of all returned bodies never
    exceeds ``max_chars``. Truncation happens at document boundaries: once
    adding the next file would exceed the budget, that file is *omitted
    entirely* (not partially appended) and a warning is logged. This keeps
    every value in the returned dict a complete document, which is what the
    LLM expects.
    """
    files = list_context_files(Path(root))
    out: dict[str, str] = {}
    used = 0
    truncated: list[str] = []
    for p in files:
        rel = _relative(Path(root), p)
        try:
            body = p.read_text(encoding="utf-8")
        except OSError as exc:  # pragma: no cover — defensive
            _log.warning("Could not read context file %s: %s", p, exc)
            continue
        if used + len(body) > max_chars:
            truncated.append(rel)
            continue
        out[rel] = body
        used += len(body)
    if truncated:
        _log.warning(
            "load_context truncated %d file(s) at max_chars=%d: %s",
            len(truncated),
            max_chars,
            ", ".join(truncated),
        )
    return out


def _first_line_or_heading(text: str) -> str:
    """Return the first markdown heading, or the first non-empty line."""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            return line.lstrip("#").strip()
        return line
    return ""


def context_summary(root: Path) -> str:
    """One-line-per-file index of `.i2e/context/`.

    Format: ``"<relative_path>: <first heading or first line>"``. Files with no
    readable content are listed with an empty summary. Returns an empty string
    when there are no context files (no trailing newline).
    """
    files = list_context_files(Path(root))
    lines: list[str] = []
    for p in files:
        rel = _relative(Path(root), p)
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:  # pragma: no cover — defensive
            text = ""
        headline = _first_line_or_heading(text)
        lines.append(f"{rel}: {headline}" if headline else f"{rel}:")
    return "\n".join(lines)
