"""Intent-change watcher — the deterministic core of the `i2e-watch` skill.

`i2e-watch` runs a continuous loop: block until an intent file under
`.i2e/intents/` changes, then hand the skill a batch of capabilities to
develop. This module is the deterministic half — it never writes code and
never invokes an LLM. The skill drives develop + evidence on the batch.

Public entry points
-------------------
- :func:`plan` — non-blocking scan. Returns the :class:`WatchBatch` that
  *would* be dispatched right now. Does not touch the watch-state file.
- :func:`next_batch` — blocks until there is a non-empty batch (or until an
  optional timeout). Records the dispatched batch in the watch-state file so
  the same intent version is never dispatched twice.

Trigger model
-------------
A capability is a **trigger** when it needs develop (no `current.yaml`, or
the intent `version` is ahead of the recorded `intent_version`) AND its
`version` is greater than the version last dispatched by the watcher
(tracked in ``.i2e/.watch_state.json``).

Keying the trigger off the intent **version** — not the file mtime — is what
makes the watcher robust: the orchestrator's ``runtime:`` frontmatter mirror
rewrites intent files mid-develop, and a mtime-based watcher would treat its
own dispatch as a fresh change and loop forever. A ``runtime:`` write never
bumps ``version``, so it never re-triggers. A develop that fails also never
re-triggers (its version is already recorded) — the human must re-bump the
intent to retry, which is explicit and predictable.

The batch is capped at ``watch.max_concurrent`` and greedy-selected so no
two members have overlapping ``touches:`` globs (same rule as the swarm
batch planner). Triggers left over land in :attr:`WatchBatch.remaining`.

CLI
---
``python -m i2e_core.watch plan`` — print the current batch as JSON (no
state write). ``python -m i2e_core.watch next [--timeout S]`` — block for a
batch, print it as JSON, record it.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .config import load_config
from .deps import build_graph, ready_slugs
from .evidence import read_current
from .intent import Capability, parse_intent
from .io_utils import atomic_write
from .paths import i2e_dir, intents_dir
from .swarm import claim_is_stale, read_claim, worktrees_root
from .touches import paths_overlap

# A worktree claim older than this is treated as abandoned (a crashed
# instance) — matches the orchestrator's TTL so the two agree on liveness.
_CLAIM_TTL_MINUTES = 60


# ---------- watch-state file ----------


def watch_state_path(root: Path) -> Path:
    """Return ``.i2e/.watch_state.json`` for ``root`` (does not create it)."""
    return i2e_dir(Path(root)) / ".watch_state.json"


def _read_state(root: Path) -> dict[str, int]:
    """Return ``{slug: last_dispatched_version}``; ``{}`` if absent/corrupt."""
    p = watch_state_path(root)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        k: v
        for k, v in data.items()
        if isinstance(k, str) and isinstance(v, int)
    }


def _write_state(root: Path, state: dict[str, int]) -> None:
    p = watch_state_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(p, json.dumps(state, indent=2, sort_keys=True))


# ---------- scanning ----------


def _scan(root: Path) -> list[Capability]:
    """Return active capabilities that need develop, alphabetical.

    Resilient by design: an intent file that fails to parse (a half-written
    save, a genuine syntax error) is skipped rather than crashing the
    watcher. Preflight — run by the skill — is where bad intents surface.
    """
    base = intents_dir(Path(root))
    if not base.exists():
        return []
    out: list[Capability] = []
    for path in sorted(base.glob("*.md")):
        try:
            cap = parse_intent(path)
        except Exception:
            continue
        if cap.frontmatter.status != "active":
            continue
        try:
            cur = read_current(root, cap.frontmatter.capability)
        except Exception:
            continue
        # needs_develop: no evidence yet, or the intent has been version-bumped.
        if cur is None or cur.intent_version < cap.frontmatter.version:
            out.append(cap)
    return out


def _live_claimed(root: Path) -> set[str]:
    """Return slugs with a non-stale worktree claim (in flight right now).

    A capability already being developed must not be dispatched again — by
    this watcher or by a concurrent ``i2e`` instance.
    """
    base = worktrees_root(Path(root))
    if not base.exists():
        return set()
    out: set[str] = set()
    for slug_dir in base.iterdir():
        if not slug_dir.is_dir():
            continue
        claim = read_claim(root, slug_dir.name)
        if claim is None:
            continue
        if claim_is_stale(claim, ttl_minutes=_CLAIM_TTL_MINUTES):
            continue
        out.add(claim.slug)
    return out


# ---------- batch model + planner ----------


class WatchBatch(BaseModel):
    """One watch cycle's output.

    ``batch`` is the capped, conflict-free set of capabilities to develop
    now. ``remaining`` is the triggers that were ready but did not fit (over
    the concurrency cap, or a ``touches:`` conflict) — the skill drains them
    on its next loop. ``timed_out`` is True only when :func:`next_batch` hit
    its timeout with nothing to dispatch.
    """

    model_config = ConfigDict(extra="forbid")

    batch: list[str] = Field(default_factory=list)
    remaining: list[str] = Field(default_factory=list)
    max_concurrent: int
    reason: Literal["initial", "intent-change", "timeout"]
    timed_out: bool = False


def plan(root: Path, *, max_concurrent: int | None = None) -> WatchBatch:
    """Non-blocking scan: the batch that would be dispatched right now.

    Steps:

    1. ``triggers`` = active capabilities that need develop *and* whose
       ``version`` is ahead of the watch-state record.
    2. Drop triggers held back by ``depends_on:`` (a parent still needs
       develop) or by a live worktree claim.
    3. Walk the survivors alphabetically; greedily select while
       ``len(batch) < max_concurrent`` and the candidate's ``touches:``
       globs do not overlap an already-selected member. Everything skipped
       lands in ``remaining``.

    Does not write the watch-state file — :func:`next_batch` owns that.
    """
    root = Path(root)
    if max_concurrent is None:
        max_concurrent = load_config(root).watch.max_concurrent

    state = _read_state(root)
    reason: Literal["initial", "intent-change"] = (
        "initial" if not state else "intent-change"
    )

    scoped = _scan(root)
    version_by_slug = {
        c.frontmatter.capability: c.frontmatter.version for c in scoped
    }
    touches_by_slug = {
        c.frontmatter.capability: list(c.frontmatter.touches) for c in scoped
    }

    triggers = {
        slug
        for slug, ver in version_by_slug.items()
        if ver > state.get(slug, 0)
    }
    if not triggers:
        return WatchBatch(
            batch=[], remaining=[], max_concurrent=max_concurrent, reason=reason
        )

    # depends_on: a child whose parent also needs develop must wait. Ordering
    # keys off the full scoped set, then we keep only the triggered slugs.
    graph = build_graph(root)
    ready = ready_slugs(graph, set(version_by_slug))
    claimed = _live_claimed(root)

    candidates = sorted(
        slug
        for slug in triggers
        if slug in ready and slug not in claimed
    )

    selected: list[str] = []
    remaining: list[str] = []
    for slug in candidates:
        if len(selected) >= max_concurrent:
            remaining.append(slug)
            continue
        if any(
            paths_overlap(touches_by_slug[slug], touches_by_slug[s])
            for s in selected
        ):
            remaining.append(slug)
            continue
        selected.append(slug)

    return WatchBatch(
        batch=selected,
        remaining=remaining,
        max_concurrent=max_concurrent,
        reason=reason,
    )


def _record_batch(root: Path, slugs: list[str]) -> None:
    """Mark ``slugs`` as dispatched at their current intent version.

    Only the dispatched slugs are recorded — triggers left in
    ``remaining`` keep their stale record so the next :func:`plan` re-emits
    them immediately without waiting on a fresh file change.
    """
    if not slugs:
        return
    state = _read_state(root)
    version_by_slug = {
        c.frontmatter.capability: c.frontmatter.version for c in _scan(root)
    }
    for slug in slugs:
        if slug in version_by_slug:
            state[slug] = version_by_slug[slug]
    _write_state(root, state)


# ---------- blocking watch ----------


class _IntentChangeHandler(FileSystemEventHandler):
    """Sets an :class:`~threading.Event` on any file change under intents/."""

    def __init__(self, event: threading.Event) -> None:
        self._event = event

    def on_any_event(self, event) -> None:  # noqa: ANN001 - watchdog type
        if not event.is_directory:
            self._event.set()


def _start_intents_observer(
    root: Path, changed: threading.Event
) -> Observer:
    """Start a watchdog observer over ``.i2e/intents/``; caller stops it."""
    base = intents_dir(Path(root))
    base.mkdir(parents=True, exist_ok=True)
    observer = Observer()
    observer.schedule(_IntentChangeHandler(changed), str(base), recursive=True)
    observer.start()
    return observer


def next_batch(
    root: Path,
    *,
    max_concurrent: int | None = None,
    timeout: float | None = None,
) -> WatchBatch:
    """Block until there is a non-empty batch, then record and return it.

    The observer runs for the whole call, so a change that lands between a
    :func:`plan` scan and the wait is never missed — the handler sets the
    event, which is cleared just before each scan. On ``timeout`` (seconds)
    with nothing to dispatch, returns an empty batch with ``timed_out=True``
    so the caller can loop. ``timeout=None`` blocks indefinitely.
    """
    root = Path(root)
    if max_concurrent is None:
        max_concurrent = load_config(root).watch.max_concurrent
    debounce_s = max(load_config(root).watch.debounce_ms, 0) / 1000.0

    deadline = None if timeout is None else time.monotonic() + timeout
    changed = threading.Event()
    observer = _start_intents_observer(root, changed)
    try:
        while True:
            changed.clear()
            result = plan(root, max_concurrent=max_concurrent)
            if result.batch:
                _record_batch(root, result.batch)
                return result

            if deadline is None:
                wait_for: float | None = None
            else:
                wait_for = deadline - time.monotonic()
                if wait_for <= 0:
                    return WatchBatch(
                        batch=[],
                        remaining=[],
                        max_concurrent=max_concurrent,
                        reason="timeout",
                        timed_out=True,
                    )

            if not changed.wait(timeout=wait_for):
                return WatchBatch(
                    batch=[],
                    remaining=[],
                    max_concurrent=max_concurrent,
                    reason="timeout",
                    timed_out=True,
                )
            # Coalesce the rest of the write burst before re-scanning.
            time.sleep(debounce_s)
    finally:
        try:
            observer.stop()
            observer.join(timeout=2.0)
        except Exception:
            pass


# ---------- CLI ----------


def _emit(batch: WatchBatch) -> None:
    print(json.dumps(batch.model_dump(mode="json"), sort_keys=True), flush=True)


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m i2e_core.watch",
        description="Watch .i2e/intents/ and plan develop batches.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser(
        "plan", help="Print the batch that would dispatch now (no wait)."
    )
    p_plan.add_argument("--root", default=".", help="Project root (cwd).")
    p_plan.add_argument(
        "--max", type=int, default=None, help="Override watch.max_concurrent."
    )

    p_next = sub.add_parser(
        "next", help="Block until a batch is ready, then print + record it."
    )
    p_next.add_argument("--root", default=".", help="Project root (cwd).")
    p_next.add_argument(
        "--max", type=int, default=None, help="Override watch.max_concurrent."
    )
    p_next.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Seconds to wait before returning an empty timed-out batch.",
    )

    args = parser.parse_args(argv)
    root = Path(args.root)

    if args.cmd == "plan":
        _emit(plan(root, max_concurrent=args.max))
        return 0
    if args.cmd == "next":
        _emit(
            next_batch(
                root, max_concurrent=args.max, timeout=args.timeout
            )
        )
        return 0
    return 1  # pragma: no cover - argparse 'required' guards this


if __name__ == "__main__":  # pragma: no cover - thin CLI shim
    raise SystemExit(_main(sys.argv[1:]))


__all__ = [
    "WatchBatch",
    "next_batch",
    "plan",
    "watch_state_path",
]
