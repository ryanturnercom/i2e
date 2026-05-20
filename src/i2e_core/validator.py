"""Forced-evidence rules per spec §5, plus config-aware effort validation."""

from __future__ import annotations

from typing import Iterable

from .config import I2EConfig
from .intent import Capability, Constraint, EvidenceItem


class ValidationError(Exception):
    """Aggregated validation failures."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors) if errors else "validation failed")
        self.errors: list[str] = list(errors)


def _items(cap: Capability) -> Iterable[EvidenceItem | Constraint]:
    yield from cap.evidence
    yield from cap.constraints


def validate_capability(
    cap: Capability,
    installed_providers: set[str] | None = None,
) -> None:
    """Apply the three forced-evidence rules; raise on failure."""
    errors: list[str] = []

    # Rule 1: items must declare a provider. Pydantic enforces this; surface
    # a friendly message if a legacy / dict path somehow yields an empty string.
    for it in _items(cap):
        if not getattr(it, "provider", None):
            errors.append(
                f"Item {it.id!r} has no provider (rule 1: every item names a provider)"
            )

    # Rule 2: provider must be an installed i2e-provider-* skill.
    if installed_providers is not None:
        for it in _items(cap):
            if it.provider and it.provider not in installed_providers:
                errors.append(
                    f"Item {it.id!r} names provider {it.provider!r} but no matching "
                    f"i2e-provider-* skill is installed"
                )

    # Rule 3: at least one evidence item or constraint.
    if len(cap.evidence) + len(cap.constraints) == 0:
        errors.append(
            "Capability has no evidence or constraints — every intent needs at "
            "least one way to know it worked"
        )

    if errors:
        raise ValidationError(errors)


def validate_capability_with_config(
    cap: Capability,
    cfg: I2EConfig,
    installed_providers: set[str] | None = None,
) -> None:
    """Run forced-evidence rules and check effort tiers against config."""
    errors: list[str] = []
    try:
        validate_capability(cap, installed_providers=installed_providers)
    except ValidationError as exc:
        errors.extend(exc.errors)

    case_tiers = set(cfg.effort_tiers.case)
    target_tiers = set(cfg.effort_tiers.target)
    for it in cap.evidence:
        valid = case_tiers if it.type == "case" else target_tiers
        if it.effort not in valid:
            errors.append(
                f"Item {it.id!r} has unknown effort {it.effort!r} for type "
                f"{it.type!r}; valid: {sorted(valid)}"
            )
    for it in cap.constraints:
        if it.effort not in case_tiers:
            errors.append(
                f"Constraint {it.id!r} has unknown effort {it.effort!r}; "
                f"valid: {sorted(case_tiers)}"
            )

    if errors:
        raise ValidationError(errors)


def format_errors(err: ValidationError) -> str:
    """Human-readable bullet list of errors."""
    if not err.errors:
        return "(no errors)"
    return "\n".join(f"  - {e}" for e in err.errors)
