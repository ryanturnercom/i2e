"""Swarm tick primitives — worktree-as-lock atomic claim.

The orchestrator's parallel batch path (spec §6.1, v2 sliced design)
needs a race-safe "is this capability already being worked on?" check
that survives concurrent ticks on POSIX and Windows alike. The cheapest
primitive that gives us this is directory existence:

* :func:`acquire_claim` calls ``os.makedirs(.i2e/worktrees/<slug>/,
  exist_ok=False)`` — atomic CAS on directory existence.
* On success, a sibling :class:`Claim` is serialised to ``claim.json``
  inside the worktree so a later sweep can tell a live claim from a
  stale one.
* :func:`is_pid_alive` is the load-bearing liveness check; the function
  intentionally treats ``PermissionError`` as "alive" because a process
  we cannot signal must still exist on the box.

This module is small on purpose: later slices build the `runtime:`
frontmatter mirror, batch planner, and worktree dispatcher on top of
these primitives. They are NOT folded in here.
"""

from __future__ import annotations

import concurrent.futures as _cf
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from .io_utils import atomic_write
from .paths import i2e_dir, intents_dir


Step = Literal["develop", "evidence", "adapt"]


class Claim(BaseModel):
    """The on-disk record of one in-flight capability claim.

    The worktree directory itself is the lock. This file is the
    human-readable record of *who* holds it. It carries everything a
    stale-claim sweep or a dashboard needs: the agent / session running
    it, the OS process id (for liveness), the tick that opened it, and
    the current pipeline step.
    """

    model_config = ConfigDict(extra="forbid")

    slug: str
    agent_id: str
    session_id: str | None = None
    pid: int
    tick_id: str
    step: Step
    started_at: datetime
    progress: str = ""


def worktrees_root(root: Path) -> Path:
    """Return ``.i2e/worktrees/`` for ``root`` (does not create it)."""
    return i2e_dir(Path(root)) / "worktrees"


def worktree_dir(root: Path, slug: str) -> Path:
    """Return ``.i2e/worktrees/<slug>/`` for ``root``."""
    return worktrees_root(root) / slug


def claim_path(root: Path, slug: str) -> Path:
    return worktree_dir(root, slug) / "claim.json"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def is_pid_alive(pid: int) -> bool:
    """Return True iff ``pid`` names a currently-running OS process.

    Implementation notes:

    * On POSIX, ``os.kill(pid, 0)`` sends no signal but raises
      :class:`ProcessLookupError` when ``pid`` is dead. A
      :class:`PermissionError` means the process exists but is owned by
      a user we cannot signal — still "alive" for our purposes.
    * On Windows we open the process with ``PROCESS_QUERY_LIMITED_INFORMATION``
      and check ``GetExitCodeProcess`` against the magic value 259
      (``STILL_ACTIVE``). A failed open with last-error
      ``ERROR_ACCESS_DENIED`` (5) also implies a live process we lack
      rights to inspect.
    * ``pid <= 0`` is treated as dead regardless of platform.
    """
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
        except Exception:
            return False
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        ERROR_ACCESS_DENIED = 5
        STILL_ACTIVE = 259
        k = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = k.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return ctypes.get_last_error() == ERROR_ACCESS_DENIED
        try:
            exit_code = ctypes.c_ulong()
            ok = k.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            if not ok:
                return False
            return exit_code.value == STILL_ACTIVE
        finally:
            k.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def read_claim(root: Path, slug: str) -> Claim | None:
    """Return the claim file for ``slug``, or ``None`` if none exists.

    A worktree directory without a claim.json is treated as no claim —
    the file race-loses to the directory and a recovery path should
    drop the empty directory rather than block on it.
    """
    p = claim_path(root, slug)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    try:
        return Claim.model_validate(data)
    except Exception:
        return None


def _write_claim(claim: Claim, root: Path) -> Path:
    target = claim_path(root, claim.slug)
    atomic_write(target, json.dumps(claim.model_dump(mode="json"), indent=2))
    return target


def acquire_claim(
    root: Path,
    slug: str,
    *,
    tick_id: str,
    step: Step,
    agent_id: str | None = None,
    session_id: str | None = None,
    progress: str = "",
) -> Claim:
    """Try to claim ``slug``. Returns the :class:`Claim` on success.

    Raises :class:`FileExistsError` if the worktree directory already
    exists AND the recorded PID is alive. If the recorded PID is dead
    the stale worktree is swept (directory removed) and the claim is
    re-acquired. A directory with no readable ``claim.json`` is also
    treated as stale.
    """
    base = worktrees_root(Path(root))
    base.mkdir(parents=True, exist_ok=True)
    target = worktree_dir(root, slug)
    try:
        os.makedirs(target, exist_ok=False)
    except FileExistsError:
        existing = read_claim(root, slug)
        if existing is not None and is_pid_alive(existing.pid):
            raise
        # Stale claim (or empty worktree). Sweep and retry once.
        _remove_worktree(target)
        os.makedirs(target, exist_ok=False)

    claim = Claim(
        slug=slug,
        agent_id=agent_id or str(uuid.uuid4()),
        session_id=session_id,
        pid=os.getpid(),
        tick_id=tick_id,
        step=step,
        started_at=_now_utc(),
        progress=progress,
    )
    _write_claim(claim, root)
    return claim


def release_claim(root: Path, slug: str) -> bool:
    """Drop the worktree directory for ``slug``.

    Returns ``True`` if a worktree was removed, ``False`` if nothing
    was there. Idempotent — safe to call after a crash recovery.
    """
    target = worktree_dir(root, slug)
    if not target.exists():
        return False
    _remove_worktree(target)
    return True


def _remove_worktree(target: Path) -> None:
    """Best-effort recursive removal of a worktree directory."""
    if not target.exists():
        return
    # Use os.walk(topdown=False) so children are removed before parents.
    for sub_root, dirs, files in os.walk(target, topdown=False):
        sub = Path(sub_root)
        for f in files:
            try:
                (sub / f).unlink()
            except FileNotFoundError:
                pass
        for d in dirs:
            try:
                (sub / d).rmdir()
            except (FileNotFoundError, OSError):
                pass
    try:
        target.rmdir()
    except (FileNotFoundError, OSError):
        pass


def sweep_stale(root: Path, slug: str) -> bool:
    """Reclaim a worktree whose claim names a dead PID.

    Returns ``True`` if the worktree was removed (caller may retry the
    claim), ``False`` if the claim is still live or no worktree exists.
    """
    target = worktree_dir(root, slug)
    if not target.exists():
        return False
    claim = read_claim(root, slug)
    if claim is None:
        # No claim file: treat as orphaned, sweep it.
        _remove_worktree(target)
        return True
    if is_pid_alive(claim.pid):
        return False
    _remove_worktree(target)
    return True


def claim_is_stale(
    claim: Claim,
    *,
    ttl_minutes: int = 60,
    now: datetime | None = None,
) -> bool:
    """Return True when ``claim`` should be treated as abandoned.

    A claim is stale when the process that wrote it is gone, or when it
    has been held longer than ``ttl_minutes``. The TTL backstop covers a
    recycled PID and the per-tick CLI mode where each tick is a fresh,
    short-lived process — either signal frees the capability for another
    instance to take over.
    """
    if not is_pid_alive(claim.pid):
        return True
    started = claim.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    ref = now or _now_utc()
    return ref - started > timedelta(minutes=ttl_minutes)


__all__ = [
    "Claim",
    "DispatchReport",
    "DispatchResult",
    "Step",
    "acquire_claim",
    "claim_is_stale",
    "claim_path",
    "clear_runtime",
    "dispatch_batch",
    "is_pid_alive",
    "mirror_runtime",
    "plan_batch",
    "read_claim",
    "read_runtime",
    "release_claim",
    "runtime_block_for",
    "sweep_stale",
    "worktree_dir",
    "worktrees_root",
]


# ---------- runtime-frontmatter mirror ----------
#
# The runtime: block is the human-readable surface for an active claim.
# It is NOT the lock — only the worktree directory is. The orchestrator
# writes runtime: after a successful acquire_claim and clears it on
# release_claim or stale sweep. i2e-intent must never touch this field.


def runtime_block_for(claim: Claim, *, worktree_rel: str) -> dict[str, object]:
    """Build the runtime: frontmatter block payload from a Claim."""
    return {
        "agent_id": claim.agent_id,
        "session_id": claim.session_id,
        "tick_id": claim.tick_id,
        "step": claim.step,
        "started_at": claim.started_at.isoformat(),
        "worktree": worktree_rel,
    }


def _intent_path(root: Path, slug: str) -> Path:
    return intents_dir(Path(root)) / f"{slug}.md"


def _worktree_rel(root: Path, slug: str) -> str:
    base = Path(root).resolve()
    target = worktree_dir(base, slug)
    try:
        rel = target.relative_to(base)
    except ValueError:
        rel = target
    return str(rel).replace("\\", "/")


def mirror_runtime(root: Path, claim: Claim) -> Path | None:
    """Add the runtime: block to ``claim.slug``'s intent file.

    Returns the intent path on success, ``None`` if the intent file does
    not exist (a swarm tick on a draft slug, say). Every other
    frontmatter field is preserved — this is the orchestrator's carve-out
    to write a single field on an active intent.
    """
    # Local import: swarm and intent both import from io_utils; routing
    # the heavier intent imports lazily keeps the swarm module light.
    from .intent import Frontmatter, parse_intent, write_intent

    root_p = Path(root)
    path = _intent_path(root_p, claim.slug)
    if not path.exists():
        return None
    cap = parse_intent(path)
    fm_dict = cap.frontmatter.model_dump(mode="json")
    fm_dict["runtime"] = runtime_block_for(
        claim, worktree_rel=_worktree_rel(root_p, claim.slug)
    )
    new_fm = Frontmatter.model_validate(fm_dict)
    new_cap = cap.model_copy(update={"frontmatter": new_fm})
    write_intent(new_cap, path)
    return path


def clear_runtime(root: Path, slug: str) -> Path | None:
    """Remove the runtime: block from ``slug``'s intent file.

    Idempotent — returns ``None`` if the intent file doesn't exist OR
    if there was no runtime block to clear. Otherwise returns the
    rewritten intent path.
    """
    from .intent import Frontmatter, parse_intent, write_intent

    path = _intent_path(Path(root), slug)
    if not path.exists():
        return None
    cap = parse_intent(path)
    if cap.frontmatter.runtime is None:
        return None
    fm_dict = cap.frontmatter.model_dump(mode="json")
    fm_dict["runtime"] = None
    new_fm = Frontmatter.model_validate(fm_dict)
    new_cap = cap.model_copy(update={"frontmatter": new_fm})
    write_intent(new_cap, path)
    return path


def read_runtime(root: Path, slug: str) -> dict | None:
    """Return the runtime: block dict from an intent, or ``None``."""
    from .intent import parse_intent

    path = _intent_path(Path(root), slug)
    if not path.exists():
        return None
    cap = parse_intent(path)
    return cap.frontmatter.runtime


# ---------- batch tick planner ----------


def plan_batch(root: Path) -> list[str]:
    """Return the slugs to dispatch this tick as one parallel batch.

    Algorithm:

    1. ``eligible`` = capabilities that need develop (the existing
       ``scoped_capabilities`` set).
    2. ``ready`` = eligible slugs whose ``depends_on:`` parents are all
       *outside* eligible (topo respect, computed by :func:`ready_slugs`).
       Preflight already rejected unknown refs and cycles, so the DAG
       always has at least one source when eligible is non-empty.
    3. Walk ``ready`` alphabetically; greedily pick a slug iff its
       ``touches:`` globs don't overlap any already-selected slug.

    A single-capability project produces a one-element batch (no batch
    overhead). A shippable project produces an empty list.
    """
    from .deps import build_graph, ready_slugs
    from .develop import scoped_capabilities
    from .touches import paths_overlap

    root_p = Path(root)
    scoped = scoped_capabilities(root_p)
    if not scoped:
        return []

    graph = build_graph(root_p)
    eligible: set[str] = {c.frontmatter.capability for c in scoped}
    ready = ready_slugs(graph, eligible)
    if not ready:
        return []

    touches_by_slug: dict[str, list[str]] = {
        c.frontmatter.capability: list(c.frontmatter.touches) for c in scoped
    }

    selected: list[str] = []
    for slug in sorted(ready):
        if any(
            paths_overlap(touches_by_slug[slug], touches_by_slug[s])
            for s in selected
        ):
            continue
        selected.append(slug)
    return selected


# ---------- worktree dispatch + merge ----------


class DispatchResult(BaseModel):
    """Per-slug outcome of one batch tick dispatch."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    ok: bool
    error: str | None = None


class DispatchReport(BaseModel):
    """Aggregate of one ``dispatch_batch`` call."""

    model_config = ConfigDict(extra="forbid")

    results: list[DispatchResult] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results)

    @property
    def slugs_completed(self) -> list[str]:
        return [r.slug for r in self.results if r.ok]


def dispatch_batch(
    root: Path,
    batch: list[str],
    *,
    tick_id: str,
    worker: Callable[[str, Claim], None],
    step: Step = "develop",
    session_id: str | None = None,
) -> DispatchReport:
    """Run a planner-produced batch in parallel.

    For each slug in ``batch`` (concurrently when len > 1):

    1. :func:`acquire_claim` — atomic ``os.makedirs`` CAS.
    2. :func:`mirror_runtime` — write the human-readable mirror.
    3. ``worker(slug, claim)`` — the seam. Production wires this to the
       Agent tool with ``isolation: worktree``; tests pass a recording
       fake.
    4. :func:`clear_runtime` + :func:`release_claim` — release the lock
       on success or hard failure. The lifecycle MUST be symmetric: a
       crashed worker leaves a stale worktree behind, and the next tick
       sweeps it via :func:`sweep_stale`.

    Each slug runs in isolation: an exception in one worker is recorded
    against that slug only and does not block siblings. Returns a
    :class:`DispatchReport` describing per-slug success / failure.
    """
    if not batch:
        return DispatchReport(results=[])

    def _run_one(slug: str) -> DispatchResult:
        try:
            claim = acquire_claim(
                root,
                slug,
                tick_id=tick_id,
                step=step,
                session_id=session_id,
            )
        except FileExistsError as e:
            return DispatchResult(slug=slug, ok=False, error=f"claim held: {e}")
        try:
            mirror_runtime(root, claim)
            worker(slug, claim)
            return DispatchResult(slug=slug, ok=True)
        except Exception as e:
            return DispatchResult(slug=slug, ok=False, error=str(e))
        finally:
            # Release in both paths — the lock primitive must be symmetric.
            try:
                clear_runtime(root, slug)
            except Exception:
                pass
            try:
                release_claim(root, slug)
            except Exception:
                pass

    if len(batch) == 1:
        return DispatchReport(results=[_run_one(batch[0])])

    results: list[DispatchResult] = []
    with _cf.ThreadPoolExecutor(max_workers=len(batch)) as pool:
        futures = {pool.submit(_run_one, slug): slug for slug in batch}
        for fut in _cf.as_completed(futures):
            results.append(fut.result())
    # Deterministic order in the report regardless of completion order.
    results.sort(key=lambda r: r.slug)
    return DispatchReport(results=results)
