"""Project scaffolding — create the ``.i2e/`` layout on first run.

I2E historically had no install step: ``.i2e/`` only appeared as a side
effect of the first file written beneath it (an intent authored by
``i2e-intent``). This module makes initialisation explicit and idempotent.
Existing directories are left alone; existing scripts are left alone unless
``force_scripts`` is set.

It also installs the ``start.sh`` / ``stop.sh`` / ``restart.sh`` helper
scripts — shipped as package data under ``i2e_core/scaffold/`` — into the
new ``.i2e/`` so operators can drive ``i2e-serve`` without hunting docs.

CLI: ``python -m i2e_core.init [--root PATH] [--force-scripts]``.
"""

from __future__ import annotations

import argparse
import json
import stat
import sys
from importlib import resources
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .paths import (
    context_dir,
    evidence_root,
    i2e_dir,
    intents_dir,
    logs_dir,
    pending_dir,
    specs_dir,
)

# Helper scripts shipped as package data (i2e_core/scaffold/*.sh) and copied
# verbatim into a fresh project's .i2e/ directory.
SCRIPT_NAMES: tuple[str, ...] = ("start.sh", "stop.sh", "restart.sh")

_EXEC_BITS = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH


class InitResult(BaseModel):
    """A record of exactly what :func:`init_project` changed.

    All paths are absolute. ``skipped`` lists scripts that were already
    present and therefore left untouched.
    """

    model_config = ConfigDict(extra="forbid")

    root: Path
    created_dirs: list[Path] = Field(default_factory=list)
    copied_scripts: list[Path] = Field(default_factory=list)
    skipped: list[Path] = Field(default_factory=list)

    @property
    def changed(self) -> bool:
        """True iff anything was created or copied on disk."""
        return bool(self.created_dirs or self.copied_scripts)


def scaffold_dirs(root: Path) -> list[Path]:
    """Return the canonical ``.i2e/`` directory layout, in stable order."""
    root = Path(root)
    return [
        i2e_dir(root),
        intents_dir(root),
        evidence_root(root),
        pending_dir(root),
        logs_dir(root),
        context_dir(root),
        specs_dir(root),
    ]


def _script_bytes(name: str) -> bytes:
    """Read a scaffold script from package data, preserving exact bytes."""
    return resources.files(__package__).joinpath("scaffold", name).read_bytes()


def init_project(root: Path, *, force_scripts: bool = False) -> InitResult:
    """Create the ``.i2e/`` layout and install the helper scripts.

    Idempotent: directories that already exist are left alone; helper
    scripts that already exist are skipped unless ``force_scripts`` is
    True. Returns an :class:`InitResult` describing what changed.
    """
    root = Path(root).resolve()
    result = InitResult(root=root)

    for d in scaffold_dirs(root):
        if d.is_dir():
            continue
        d.mkdir(parents=True, exist_ok=True)
        result.created_dirs.append(d)

    ldir = i2e_dir(root)
    for name in SCRIPT_NAMES:
        dest = ldir / name
        if dest.exists() and not force_scripts:
            result.skipped.append(dest)
            continue
        dest.write_bytes(_script_bytes(name))
        # Mark executable for POSIX shells. Harmless on Windows.
        dest.chmod(dest.stat().st_mode | _EXEC_BITS)
        result.copied_scripts.append(dest)

    return result


# ---------- CLI ----------


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m i2e_core.init",
        description="Scaffold the .i2e/ directory layout for a project.",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Project root to initialise. Defaults to cwd.",
    )
    parser.add_argument(
        "--force-scripts",
        action="store_true",
        help="Overwrite start.sh/stop.sh/restart.sh even if they exist.",
    )
    args = parser.parse_args(argv)

    result = init_project(Path(args.root), force_scripts=args.force_scripts)
    print(json.dumps(result.model_dump(mode="json"), sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - thin CLI shim
    raise SystemExit(_main(sys.argv[1:]))


__all__ = [
    "InitResult",
    "SCRIPT_NAMES",
    "init_project",
    "scaffold_dirs",
]
