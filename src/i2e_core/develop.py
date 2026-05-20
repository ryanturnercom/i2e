"""Deterministic helpers for the `i2e-develop` skill.

The actual code-writing is LLM-side; this module is the deterministic core:

* :func:`diff_against_current` — what changed since the last evidence run
* :func:`suggested_src_paths` / :func:`suggested_test_paths` — convention defaults
* :func:`develop_summary` — single-line log entry for `.i2e/logs/<tick>.yaml`
* :func:`needs_develop` / :func:`scoped_capabilities` — idempotency
* :func:`plan_develop` / :func:`execute_plan` — fan-out planning for parallel
  sub-agent writes when a capability touches multiple independent files
"""

from __future__ import annotations

import concurrent.futures as _cf
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, ConfigDict, Field

from .evidence import read_current
from .intent import Capability, Constraint, EvidenceItem, parse_intent
from .paths import intents_dir
from .touches import matches_any

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


# ---------- fan-out planning ----------


class FileGoal(BaseModel):
    """One file's worth of develop work in a fan-out plan.

    A goal is the unit a sub-agent picks up — write the file at ``path``
    such that the listed evidence/constraint ids would pass. ``description``
    is a one-liner the orchestrator uses when dispatching.
    """

    model_config = ConfigDict(extra="forbid")

    path: Path
    item_ids: list[str]
    description: str


class DevelopPlan(BaseModel):
    """Fan-out plan for a develop run.

    ``batches`` is an ordered list of parallel batches: every :class:`FileGoal`
    inside one batch targets a distinct file, so the batch may run with one
    sub-agent per goal. Successive batches run sequentially. Items whose
    suggested file path falls outside the capability's declared ``touches:``
    are recorded under :attr:`skipped_out_of_scope` and excluded from any
    batch — the planner refuses to emit a goal that the post-develop check
    would later reject.
    """

    model_config = ConfigDict(extra="forbid")

    capability: str
    batches: list[list[FileGoal]] = Field(default_factory=list)
    skipped_out_of_scope: list[tuple[str, str]] = Field(default_factory=list)

    @property
    def is_fanout(self) -> bool:
        """True iff the plan ever runs more than one goal in parallel."""
        return any(len(b) > 1 for b in self.batches)

    @property
    def total_goals(self) -> int:
        return sum(len(b) for b in self.batches)


def _normalize(p: Path | str) -> str:
    return str(p).replace("\\", "/")


def _goal_path(
    item: EvidenceItem | Constraint, cap: Capability
) -> Path | None:
    """Pick the target file for one item's develop goal.

    Pytest items have a clear convention (the file in the nodeid).
    Other providers fall back to the capability's default ``src/`` path so
    every Case still gets some sub-agent assignment. ``None`` means no
    sensible file — the planner skips the item.
    """
    p = suggested_test_paths(item)
    if p is not None:
        return p
    srcs = suggested_src_paths(cap)
    return srcs[0] if srcs else None


def plan_develop(cap: Capability) -> DevelopPlan:
    """Group develop work by file, with same-file goals serialized.

    Algorithm:

    1. Each evidence item + constraint contributes one goal aimed at its
       target file (test file for pytest items, capability ``src/`` default
       otherwise).
    2. Goals whose target falls outside the capability's ``touches:`` globs
       are dropped into ``skipped_out_of_scope`` instead of being scheduled.
    3. Goals are clustered by file; within a cluster they preserve declared
       order. Across files, the i-th goal of every cluster forms batch i —
       so distinct files run in parallel, same file serializes.

    A single-file capability produces exactly one batch containing one goal:
    no fan-out overhead, identical to the pre-fanout behaviour.
    """
    touches = cap.frontmatter.touches or ["**"]

    items: list[tuple[str, EvidenceItem | Constraint]] = []
    for it in cap.evidence:
        items.append((it.type, it))
    for con in cap.constraints:
        items.append(("constraint", con))

    goals_by_file: dict[str, list[FileGoal]] = {}
    skipped: list[tuple[str, str]] = []

    for kind, it in items:
        path = _goal_path(it, cap)
        if path is None:
            continue
        path_str = _normalize(path)
        if not matches_any(path_str, touches):
            skipped.append((it.id, path_str))
            continue
        goal = FileGoal(
            path=Path(path_str),
            item_ids=[it.id],
            description=f"{kind}: {it.id}",
        )
        goals_by_file.setdefault(path_str, []).append(goal)

    # Build batches by round-robin across file groups at each depth. Sorting
    # the file keys keeps the schedule deterministic for tests and reports.
    depths = max((len(v) for v in goals_by_file.values()), default=0)
    batches: list[list[FileGoal]] = []
    for d in range(depths):
        batch: list[FileGoal] = []
        for fpath in sorted(goals_by_file):
            queue = goals_by_file[fpath]
            if d < len(queue):
                batch.append(queue[d])
        if batch:
            batches.append(batch)

    return DevelopPlan(
        capability=cap.frontmatter.capability,
        batches=batches,
        skipped_out_of_scope=skipped,
    )


class WriteReport(BaseModel):
    """Result of executing a :class:`DevelopPlan`."""

    model_config = ConfigDict(extra="forbid")

    paths_written: list[str] = Field(default_factory=list)
    errors: list[tuple[str, str]] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def execute_plan(
    plan: DevelopPlan,
    writer: Callable[[FileGoal], str],
    *,
    root: Path | None = None,
) -> WriteReport:
    """Run a plan with ``writer(goal) -> file_contents``.

    Members of one batch are dispatched to a thread pool and run in
    parallel; batches themselves run sequentially. Each goal's returned
    string is written to ``root / goal.path``. A goal that raises is
    recorded in :attr:`WriteReport.errors` but does not block its siblings
    in the same batch.

    The writer callable is the seam tests use to substitute a sub-agent
    dispatch with a deterministic content generator. In production the
    orchestrator's writer would invoke the Agent tool, one Agent per goal.
    """
    base = Path(root) if root is not None else Path(".")
    paths_written: list[str] = []
    errors: list[tuple[str, str]] = []

    def _write_one(goal: FileGoal, content: str) -> None:
        target = base / goal.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    for batch in plan.batches:
        if len(batch) == 1:
            # Single-goal batch: no fan-out overhead.
            goal = batch[0]
            try:
                content = writer(goal)
                _write_one(goal, content)
                paths_written.append(_normalize(goal.path))
            except Exception as e:
                errors.append((_normalize(goal.path), str(e)))
            continue

        with _cf.ThreadPoolExecutor(max_workers=len(batch)) as pool:
            futures = {pool.submit(writer, g): g for g in batch}
            results: list[tuple[FileGoal, str | None, str | None]] = []
            for fut in _cf.as_completed(futures):
                g = futures[fut]
                try:
                    results.append((g, fut.result(), None))
                except Exception as e:
                    results.append((g, None, str(e)))
        # Sort results by path so paths_written stays deterministic regardless
        # of which sub-agent returned first.
        results.sort(key=lambda t: _normalize(t[0].path))
        for goal, content, err in results:
            if err is not None:
                errors.append((_normalize(goal.path), err))
                continue
            assert content is not None  # narrowed by the err branch
            try:
                _write_one(goal, content)
                paths_written.append(_normalize(goal.path))
            except Exception as e:
                errors.append((_normalize(goal.path), str(e)))

    return WriteReport(paths_written=paths_written, errors=errors)
