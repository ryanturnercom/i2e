"""Helpers for the ``touches:`` declared-file-scope field (spec §2.1, §4.1).

Each Capability declares a list of globs over the project tree (typically
``src/foo/**`` and ``tests/foo/**``). Two responsibilities live here:

* :func:`paths_overlap` — do two capabilities' globs intersect? Used by the
  swarm-tick scheduler to decide what can run in parallel.
* :func:`paths_outside_touches` — given a list of files that develop touched,
  return the ones that fall outside the declared scope. The post-develop
  check turns this into a hard error so develop can't drift.

The matching is intentionally conservative: we prefer a false "overlap" /
"violation" over silently allowing a race or a stray write. Globs that the
checker can't resolve are treated as covering the whole tree.
"""

from __future__ import annotations

import re
from pathlib import Path


def _normalize(p: str) -> str:
    """Forward-slash form, no leading ``./``, no leading/trailing slashes."""
    s = p.replace("\\", "/")
    while s.startswith("./"):
        s = s[2:]
    return s.strip("/")


def _literal_prefix(glob: str) -> str:
    """Return the longest leading run of segments with no wildcard meta-chars.

    Examples
    --------
    ``src/foo/**`` -> ``src/foo``
    ``src/foo/*.py`` -> ``src/foo``
    ``**`` -> ``""`` (matches everything)
    ``src/foo/bar`` -> ``src/foo/bar``
    """
    parts = _normalize(glob).split("/")
    out: list[str] = []
    for part in parts:
        if any(c in part for c in "*?["):
            break
        out.append(part)
    return "/".join(out)


def paths_overlap(a: list[str], b: list[str]) -> bool:
    """Return ``True`` if two glob lists could match a common path.

    Conservative — if either list contains ``**`` (or any glob whose literal
    prefix is empty), the result is ``True``. Otherwise we compare literal
    prefixes segment-by-segment so ``src/foo`` is not considered a prefix of
    ``src/foobar``.
    """
    if not a or not b:
        # An empty touches list means "no declared scope"; treat that as
        # potential overlap so the scheduler can't be tricked into a race.
        return True
    for ga in a:
        for gb in b:
            pa = _literal_prefix(ga)
            pb = _literal_prefix(gb)
            if pa == "" or pb == "":
                return True
            sa = pa.split("/")
            sb = pb.split("/")
            n = min(len(sa), len(sb))
            if sa[:n] == sb[:n]:
                return True
    return False


def _compile_glob(glob: str) -> re.Pattern[str]:
    """Translate a path glob (supporting ``**``) to an anchored regex.

    Segment-aware: ``*`` does not cross ``/``, ``**`` does. ``?`` matches any
    single non-slash character. Character classes ``[...]`` are passed through
    by escaping their contents.
    """
    g = _normalize(glob)
    if g == "" or g == "**":
        return re.compile(r".*\Z")
    out: list[str] = []
    parts = g.split("/")
    for i, part in enumerate(parts):
        if i:
            # Joiner between segments. ``**`` consumes the separator itself
            # so we emit the slash only between non-double-star segments.
            if parts[i - 1] != "**" and part != "**":
                out.append(re.escape("/"))
            else:
                # Permit either "a/**/b" matching "a/b" (no extra slash) or
                # "a/x/b": allow optional slash before/after **.
                out.append("/?")
        if part == "**":
            out.append(".*")
        else:
            seg = ""
            j = 0
            while j < len(part):
                c = part[j]
                if c == "*":
                    seg += "[^/]*"
                elif c == "?":
                    seg += "[^/]"
                elif c == "[":
                    k = part.find("]", j)
                    if k == -1:
                        seg += re.escape(c)
                    else:
                        seg += part[j : k + 1]
                        j = k
                else:
                    seg += re.escape(c)
                j += 1
            out.append(seg)
    return re.compile("".join(out) + r"\Z")


def matches_any(path: str | Path, globs: list[str]) -> bool:
    """Return True if ``path`` matches any glob in ``globs``."""
    s = _normalize(str(path))
    for g in globs:
        if _compile_glob(g).match(s):
            return True
    return False


def paths_outside_touches(
    touches: list[str], paths: list[Path] | list[str]
) -> list[str]:
    """Return the paths that are NOT covered by any of the touches globs.

    Paths are returned in normalized forward-slash form, in input order,
    deduplicated. An empty result means develop stayed in scope.
    """
    seen: set[str] = set()
    out: list[str] = []
    for p in paths:
        s = _normalize(str(p))
        if s in seen:
            continue
        seen.add(s)
        if not matches_any(s, touches):
            out.append(s)
    return out


__all__ = [
    "matches_any",
    "paths_outside_touches",
    "paths_overlap",
]
