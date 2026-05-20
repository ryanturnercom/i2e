"""Default scaffolding for a brand-new Capability.

Produces a minimal valid `Capability` so the LLM has something to walk the
user through editing. The scaffold uses ``pytest`` as the example provider so
the file passes `validate_capability(installed_providers={"pytest"})` out of
the box.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from .intent import Capability, EvidenceItem, Frontmatter


def today_utc() -> date:
    """Return today's date in UTC. Exposed so tests can monkeypatch easily."""
    return datetime.now(timezone.utc).date()


def default_capability(slug: str, watcher: str = "@me") -> Capability:
    """Return a minimal valid scaffold for ``slug``.

    The scaffold contains one example evidence item using the ``pytest``
    provider so the result passes
    ``validate_capability(installed_providers={"pytest"})``.
    """
    today = today_utc()
    fm = Frontmatter(
        capability=slug,
        created=today,
        updated=today,
        version=1,
        status="draft",
        watcher=watcher,
    )
    seed_item = EvidenceItem(
        id="first-case",
        type="case",
        provider="pytest",
        query=f"tests/test_{slug.replace('-', '_')}.py",
        expect="passes",
        effort="medium",
    )
    return Capability(
        frontmatter=fm,
        description=f"# {slug}\n\nDescribe the capability here.",
        evidence=[seed_item],
        constraints=[],
    )
