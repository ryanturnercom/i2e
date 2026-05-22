"""Capability dependency graph helpers.

Implements the ``depends_on:`` frontmatter field's validation and ordering
semantics (spec §2.1 / §6.1):

* :func:`build_graph` — slug -> declared deps for every active intent
* :func:`find_unknown_refs` — deps that reference a slug not in the graph
* :func:`find_cycle` — one cycle if the graph has any, else ``None``
* :func:`ready_slugs` — among a set of slugs needing develop, the subset whose
  deps are all outside the set (i.e. already developed or shippable)
"""

from __future__ import annotations

from pathlib import Path

from .intent import parse_intent
from .paths import intents_dir


def build_graph(root: Path) -> dict[str, list[str]]:
    """Return ``{slug: depends_on}`` for every active or shipped intent.

    Drafts and retired intents are excluded — they cannot participate in
    the ordering graph. ``shipped`` intents ARE included: a shipped
    capability is a completed, valid ``depends_on`` target. Excluding it
    would make a still-active child's dependency look like an unknown
    reference the moment its parent ships (``ready_slugs`` keys ordering
    off the active candidate set, so a shipped node never gates anything).
    """
    base = intents_dir(Path(root))
    graph: dict[str, list[str]] = {}
    if not base.exists():
        return graph
    for path in sorted(base.glob("*.md")):
        try:
            cap = parse_intent(path)
        except Exception:
            continue
        if cap.frontmatter.status not in ("active", "shipped"):
            continue
        graph[cap.frontmatter.capability] = list(cap.frontmatter.depends_on)
    return graph


def find_unknown_refs(graph: dict[str, list[str]]) -> list[tuple[str, str]]:
    """Return ``(slug, missing_dep)`` for every dep that names an unknown slug."""
    known = set(graph)
    out: list[tuple[str, str]] = []
    for slug, deps in graph.items():
        for d in deps:
            if d not in known:
                out.append((slug, d))
    out.sort()
    return out


def find_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    """Return one cycle (as an ordered slug list) if any, else ``None``.

    DFS with WHITE/GREY/BLACK coloring. A back-edge into a GREY node means
    we've found a cycle; the returned list starts and ends at the same slug
    so the caller can format it as ``a -> b -> a``.
    """
    WHITE, GREY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in graph}
    parent: dict[str, str | None] = {n: None for n in graph}

    def visit(start: str) -> list[str] | None:
        stack: list[tuple[str, int]] = [(start, 0)]
        color[start] = GREY
        while stack:
            node, idx = stack[-1]
            deps = graph.get(node, [])
            if idx >= len(deps):
                color[node] = BLACK
                stack.pop()
                continue
            stack[-1] = (node, idx + 1)
            nxt = deps[idx]
            if nxt not in color:
                continue  # unknown dep — reported separately
            if color[nxt] == GREY:
                # back-edge: reconstruct the cycle from nxt to node, then nxt.
                cycle = [nxt]
                cur = node
                while cur is not None and cur != nxt:
                    cycle.append(cur)
                    cur = parent[cur]
                cycle.append(nxt)
                cycle.reverse()
                return cycle
            if color[nxt] == WHITE:
                color[nxt] = GREY
                parent[nxt] = node
                stack.append((nxt, 0))
        return None

    for n in sorted(graph):
        if color[n] == WHITE:
            c = visit(n)
            if c is not None:
                return c
    return None


def ready_slugs(graph: dict[str, list[str]], candidates: set[str]) -> set[str]:
    """Return the candidates whose deps are all *outside* ``candidates``.

    A capability in ``candidates`` has unfinished business (needs develop). If
    any of its deps is also unfinished, it must wait. Once that dep is done
    (and so leaves ``candidates``), the child becomes ready.
    """
    out: set[str] = set()
    for slug in candidates:
        deps = graph.get(slug, [])
        if not any(d in candidates for d in deps):
            out.add(slug)
    return out


__all__ = [
    "build_graph",
    "find_cycle",
    "find_unknown_refs",
    "ready_slugs",
]
