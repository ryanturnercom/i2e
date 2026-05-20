"""Atomic writes and YAML helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def atomic_write(path: Path, data: str | bytes) -> None:
    """Write ``data`` to ``path`` via a sibling ``.tmp`` + ``os.replace``."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    if isinstance(data, str):
        tmp.write_text(data, encoding="utf-8")
    else:
        tmp.write_bytes(data)
    os.replace(tmp, path)


def dump_yaml(obj: Any) -> str:
    """YAML dump with stable key order, block style, unicode-safe."""
    return yaml.safe_dump(
        obj,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )


def load_yaml(path: Path) -> Any:
    """Load a YAML file as Python objects."""
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))
