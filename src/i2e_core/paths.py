"""Canonical filesystem path resolver for an I2E project."""

from __future__ import annotations

from pathlib import Path


def find_root(start: Path | None = None) -> Path:
    """Walk up from ``start`` until a directory containing ``.i2e/`` is found."""
    cur = Path(start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / ".i2e").is_dir():
            return candidate
    raise RuntimeError(
        "No .i2e/ directory found above "
        f"{cur}. Run `i2e-intent` first to initialise the project."
    )


def i2e_dir(root: Path) -> Path:
    return root / ".i2e"


def intents_dir(root: Path) -> Path:
    return i2e_dir(root) / "intents"


def evidence_root(root: Path) -> Path:
    return i2e_dir(root) / "evidence"


def evidence_dir(root: Path, capability: str) -> Path:
    return evidence_root(root) / capability


def runs_dir(root: Path, capability: str) -> Path:
    return evidence_dir(root, capability) / "runs"


def current_path(root: Path, capability: str) -> Path:
    return evidence_dir(root, capability) / "current.yaml"


def pending_dir(root: Path) -> Path:
    return i2e_dir(root) / "pending"


def logs_dir(root: Path) -> Path:
    return i2e_dir(root) / "logs"


def context_dir(root: Path) -> Path:
    return i2e_dir(root) / "context"


def specs_dir(root: Path) -> Path:
    return i2e_dir(root) / "specs"


def config_path(root: Path) -> Path:
    return i2e_dir(root) / "config.yaml"


def report_path(root: Path) -> Path:
    return i2e_dir(root) / "report.html"


def serve_url_path(root: Path) -> Path:
    return i2e_dir(root) / ".serve.url"
