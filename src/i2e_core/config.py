"""`.i2e/config.yaml` loader with Pydantic models and default fallback."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .io_utils import load_yaml
from .paths import config_path


class TierBudget(BaseModel):
    max_attempts: int


class EffortTiers(BaseModel):
    case: dict[str, TierBudget]
    target: dict[str, TierBudget]


class Defaults(BaseModel):
    case_effort: str = "medium"
    target_effort: str = "low"
    watcher: str = "@me"


class SchedulerConfig(BaseModel):
    cadence: str = "weekly"
    via: str = "claude-code-routine"


class ServeConfig(BaseModel):
    port: int = 4230
    open_browser: bool = True
    autoreload: bool = False


class WatchConfig(BaseModel):
    """Settings for the ``i2e-watch`` intent-change watcher.

    ``max_concurrent`` caps how many capabilities one watch cycle dispatches
    in parallel. ``debounce_ms`` coalesces a burst of intent writes (an
    editor save fires several events) into a single re-scan.
    """

    max_concurrent: int = 4
    debounce_ms: int = 400


class I2EConfig(BaseModel):
    effort_tiers: EffortTiers
    defaults: Defaults = Field(default_factory=Defaults)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    serve: ServeConfig = Field(default_factory=ServeConfig)
    watch: WatchConfig = Field(default_factory=WatchConfig)


_DEFAULT_CASE_TIERS = {
    "lazy": {"max_attempts": 0},
    "low": {"max_attempts": 3},
    "medium": {"max_attempts": 6},
    "high": {"max_attempts": 10},
}
_DEFAULT_TARGET_TIERS = {
    "lazy": {"max_attempts": 0},
    "low": {"max_attempts": 1},
    "medium": {"max_attempts": 3},
    "high": {"max_attempts": 5},
}


def _default_dict() -> dict:
    return {
        "effort_tiers": {
            "case": dict(_DEFAULT_CASE_TIERS),
            "target": dict(_DEFAULT_TARGET_TIERS),
        },
        "defaults": {
            "case_effort": "medium",
            "target_effort": "low",
            "watcher": "@me",
        },
        "scheduler": {
            "cadence": "weekly",
            "via": "claude-code-routine",
        },
        "serve": {
            "port": 4230,
            "open_browser": True,
            "autoreload": False,
        },
        "watch": {
            "max_concurrent": 4,
            "debounce_ms": 400,
        },
    }


def default_config() -> I2EConfig:
    """Return a fully-defaulted config (no user file)."""
    return I2EConfig.model_validate(_default_dict())


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(root: Path | None = None) -> I2EConfig:
    """Read ``<root>/.i2e/config.yaml`` (if present) and merge with defaults."""
    base = _default_dict()
    if root is None:
        return I2EConfig.model_validate(base)
    cfg_file = config_path(Path(root))
    if not cfg_file.exists():
        return I2EConfig.model_validate(base)
    loaded = load_yaml(cfg_file) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"{cfg_file} must contain a YAML mapping at top level")
    merged = _deep_merge(base, loaded)
    return I2EConfig.model_validate(merged)


def resolve_max_attempts(
    cfg: I2EConfig,
    item_type: Literal["case", "target", "constraint"],
    effort: str,
) -> int:
    """Resolve ``effort`` into a budget; constraints share the case map."""
    if item_type == "constraint":
        tier_map = cfg.effort_tiers.case
        kind_label = "case"
    elif item_type == "case":
        tier_map = cfg.effort_tiers.case
        kind_label = "case"
    elif item_type == "target":
        tier_map = cfg.effort_tiers.target
        kind_label = "target"
    else:
        raise ValueError(f"Unknown item_type: {item_type!r}")
    if effort not in tier_map:
        valid = ", ".join(sorted(tier_map))
        raise ValueError(
            f"Unknown effort {effort!r} for {kind_label}; valid: {valid}"
        )
    return tier_map[effort].max_attempts
