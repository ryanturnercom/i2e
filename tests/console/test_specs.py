"""Specs view — list + detail + reconcile Job dispatch."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from i2e_core.console.actions.reconcile import reconcile_spec
from i2e_core.console.jobs.registry import JobRegistry
from i2e_core.console.sse import ChangeBroker
from i2e_core.console.views.specs import render_spec_detail, render_specs_list
from i2e_core.intent import (
    Capability,
    EvidenceItem,
    Frontmatter,
    parse_intent,
    write_intent,
)


def _seed_spec(root: Path, slug: str, body: str = "## Section A\nbody\n") -> Path:
    specs = root / ".i2e" / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    path = specs / f"{slug}.md"
    path.write_text(f"# {slug}\n\n{body}", encoding="utf-8")
    return path


def _seed_intent_for_spec(root: Path, slug: str, spec_slug: str, status: str = "active") -> Path:
    intents = root / ".i2e" / "intents"
    intents.mkdir(parents=True, exist_ok=True)
    today = date.today()
    cap = Capability(
        frontmatter=Frontmatter(
            capability=slug,
            created=today,
            updated=today,
            version=1,
            status=status,
            watcher="@me",
            spec=spec_slug,
            spec_section="1",
        ),
        description="x",
        evidence=[
            EvidenceItem(
                id=f"{slug}-case",
                type="case",
                provider="pytest",
                query=f"tests/test_{slug}.py::test_x",
                expect="passes",
            )
        ],
    )
    return write_intent(cap, intents / f"{slug}.md")


def test_lists_specs(tmp_path):
    _seed_spec(tmp_path, "alpha")
    _seed_spec(tmp_path, "beta")
    html = render_specs_list(tmp_path)
    assert "alpha" in html
    assert "beta" in html
    assert 'class="specs-list"' in html


def test_shows_derived_intents(tmp_path):
    _seed_spec(tmp_path, "demo-spec")
    _seed_intent_for_spec(tmp_path, "demo-cap-1", "demo-spec")
    _seed_intent_for_spec(tmp_path, "demo-cap-2", "demo-spec", status="draft")
    # An intent under a different spec must NOT appear.
    _seed_intent_for_spec(tmp_path, "other-cap", "other-spec")

    html = render_spec_detail(tmp_path, "demo-spec")

    # The derived-intents panel lists only spec-matching intents. (The
    # shell sidebar lists every intent, so scope the check to the panel's
    # intent-link rows.)
    assert 'class="intent-link" data-slug="demo-cap-1"' in html
    assert 'class="intent-link" data-slug="demo-cap-2"' in html
    assert 'class="intent-link" data-slug="other-cap"' not in html
    assert "Derived intents (2)" in html


def test_reconcile_spawns_job(tmp_path):
    _seed_spec(tmp_path, "demo-spec", body="## New section\nbody\n")
    # An intent under a different section to force reconcile to detect change.
    _seed_intent_for_spec(tmp_path, "old-cap", "demo-spec")

    registry = JobRegistry()
    broker = ChangeBroker()
    try:
        job = reconcile_spec(tmp_path, "demo-spec", registry=registry, broker=broker)
        assert job.id
        assert job.kind == "reconcile"
        assert job.scope == "demo-spec"
        assert job.state in ("completed", "failed")
        # The Job must appear in the registry.
        assert registry.get(job.id) is not None
    finally:
        broker.close()


def test_reconcile_creates_draft_for_new_section(tmp_path):
    # A spec with two sections; only the first has a derived intent.
    # Reconcile must materialise a draft for the new section and leave the
    # pre-existing intent byte-for-byte unchanged.
    _seed_spec(
        tmp_path,
        "demo-spec",
        body="## Old Section\nold body\n\n## Brand New Section\nnew body\n",
    )
    existing = _seed_intent_for_spec(tmp_path, "old-section", "demo-spec")
    existing_before = existing.read_text(encoding="utf-8")

    registry = JobRegistry()
    broker = ChangeBroker()
    try:
        job = reconcile_spec(
            tmp_path, "demo-spec", registry=registry, broker=broker
        )
    finally:
        broker.close()
    assert job.state == "completed"

    # A draft intent for the new section now exists, with spec linkage set.
    new_path = tmp_path / ".i2e" / "intents" / "brand-new-section.md"
    assert new_path.exists()
    new_cap = parse_intent(new_path)
    assert new_cap.frontmatter.status == "draft"
    assert new_cap.frontmatter.spec == "demo-spec"
    assert new_cap.frontmatter.spec_section

    # The pre-existing intent is untouched.
    assert existing.read_text(encoding="utf-8") == existing_before
