"""Discover installed ``i2e-provider-*`` skills and load their ``provider`` modules.

Scan order (later wins on conflicts — user/project copies override the bundle):

1. ``<i2e_core install>/skills/`` (bundled with the package — always present)
2. ``~/.claude/skills/``
3. ``<project_root>/.claude/skills/``
4. Any ``extra_paths`` passed in (tests use this to inject fake skills dirs)

A skill folder is recognised by its name prefix ``i2e-provider-<name>``. The
provider helper module must be at ``<folder>/provider.py`` and must expose a
module-level ``provider`` attribute that conforms to the ``Provider`` Protocol.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Iterable

from .contract import Provider

_PREFIX = "i2e-provider-"


# ---------- path resolution ----------


def _bundled_skills_dir() -> Path:
    """Skills directory shipped inside the i2e_core package (lowest priority)."""
    return (Path(__file__).resolve().parent.parent / "skills").resolve()


def _user_skills_dir() -> Path:
    return Path("~/.claude/skills").expanduser().resolve()


def _project_skills_dir(start: Path | None = None) -> Path:
    base = Path(start or Path.cwd()).resolve()
    return (base / ".claude" / "skills").resolve()


def _candidate_dirs(extra_paths: Iterable[Path] | None) -> list[Path]:
    """Return the ordered list of skills directories to scan (lowest priority first)."""
    dirs: list[Path] = [_bundled_skills_dir(), _user_skills_dir(), _project_skills_dir()]
    if extra_paths:
        dirs.extend(Path(p).expanduser().resolve() for p in extra_paths)
    return dirs


# ---------- public API ----------


def installed_provider_names(
    extra_paths: list[Path] | None = None,
) -> set[str]:
    """Return the set of installed provider names (no ``i2e-provider-`` prefix).

    Missing directories are silently skipped — a fresh project has no skills dir.
    """
    names: set[str] = set()
    for d in _candidate_dirs(extra_paths):
        if not d.exists() or not d.is_dir():
            continue
        for entry in d.iterdir():
            if not entry.is_dir():
                continue
            if not entry.name.startswith(_PREFIX):
                continue
            names.add(entry.name[len(_PREFIX) :])
    return names


def _resolve_provider_folder(
    name: str,
    extra_paths: Iterable[Path] | None = None,
) -> Path | None:
    """Return the folder for ``name`` — later (higher-priority) wins on conflicts."""
    found: Path | None = None
    folder_name = f"{_PREFIX}{name}"
    for d in _candidate_dirs(extra_paths):
        candidate = d / folder_name
        if candidate.exists() and candidate.is_dir():
            found = candidate
    return found


# Cache keyed by (resolved-folder, provider.py mtime) so that edits invalidate.
_load_cache: dict[tuple[str, float], Provider] = {}


def load_provider(
    name: str,
    extra_paths: list[Path] | None = None,
) -> Provider:
    """Locate ``i2e-provider-<name>``, import its ``provider.py`` and return ``provider``.

    Raises ``LookupError`` (with a hint listing the scanned dirs) if not found.
    """
    folder = _resolve_provider_folder(name, extra_paths)
    if folder is None:
        scanned = "\n  - ".join(str(p) for p in _candidate_dirs(extra_paths))
        raise LookupError(
            f"Provider {name!r} not found. Scanned skills dirs:\n  - {scanned}\n"
            f"Install an i2e-provider-{name} skill in one of these locations."
        )

    provider_py = folder / "provider.py"
    if not provider_py.exists():
        raise LookupError(
            f"Provider folder {folder} is missing provider.py"
        )

    mtime = provider_py.stat().st_mtime
    cache_key = (str(provider_py.resolve()), mtime)
    cached = _load_cache.get(cache_key)
    if cached is not None:
        return cached

    module_name = f"_i2e_provider_{name}_{int(mtime)}"
    spec = importlib.util.spec_from_file_location(module_name, provider_py)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"Could not build import spec for {provider_py}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    if not hasattr(module, "provider"):
        raise AttributeError(
            f"{provider_py} does not expose a module-level `provider` attribute"
        )
    instance = module.provider
    _load_cache[cache_key] = instance
    return instance


def clear_cache() -> None:
    """Drop the module load cache (useful in tests)."""
    _load_cache.clear()


# ---------- CLI helper ----------


def _main(argv: list[str] | None = None) -> int:
    names = sorted(installed_provider_names())
    for n in names:
        print(n)
    return 0


if __name__ == "__main__":  # pragma: no cover - thin CLI shim
    raise SystemExit(_main(sys.argv[1:]))
