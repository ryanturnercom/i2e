"""Read/write `current.yaml` and per-run snapshots under `.i2e/evidence/`."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .io_utils import atomic_write, dump_yaml, load_yaml
from .paths import current_path, evidence_dir, runs_dir


Verdict = Literal[
    "pass",
    "fail",
    "met",
    "unmet",
    "trending",
    "awaiting_human",
]


class ItemVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Verdict
    value: str | None = None
    attempts_used: int = 0
    last_observed: datetime | None = None
    pending: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class CurrentEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: str
    last_run: str
    intent_version: int
    items: dict[str, ItemVerdict] = Field(default_factory=dict)


class RunSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    capability: str
    intent_version: int
    collected_at: datetime
    items: dict[str, ItemVerdict] = Field(default_factory=dict)


def _to_yaml_dict(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")


def read_current(root: Path, capability: str) -> CurrentEvidence | None:
    """Return the latest evidence snapshot, or ``None`` if absent."""
    p = current_path(Path(root), capability)
    if not p.exists():
        return None
    data = load_yaml(p) or {}
    return CurrentEvidence.model_validate(data)


def write_current(root: Path, cap: CurrentEvidence) -> Path:
    """Atomically write `current.yaml` for ``cap.capability``."""
    p = current_path(Path(root), cap.capability)
    evidence_dir(Path(root), cap.capability).mkdir(parents=True, exist_ok=True)
    atomic_write(p, dump_yaml(_to_yaml_dict(cap)))
    return p


def write_run_snapshot(root: Path, snap: RunSnapshot) -> Path:
    """Atomically write a run snapshot. Refuses overwrite (immutable)."""
    d = runs_dir(Path(root), snap.capability)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{snap.run_id}.yaml"
    if p.exists():
        raise FileExistsError(f"Run snapshot already exists: {p}")
    atomic_write(p, dump_yaml(_to_yaml_dict(snap)))
    return p


def list_runs(root: Path, capability: str) -> list[Path]:
    """Return run snapshot paths sorted chronologically (oldest first)."""
    d = runs_dir(Path(root), capability)
    if not d.exists():
        return []
    return sorted(p for p in d.iterdir() if p.suffix == ".yaml")


def read_run(path: Path) -> RunSnapshot:
    """Load a run snapshot YAML into a ``RunSnapshot``."""
    data = load_yaml(Path(path)) or {}
    return RunSnapshot.model_validate(data)
