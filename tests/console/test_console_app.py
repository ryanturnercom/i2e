"""Console router + pending view — route table, fragments, page rendering."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from i2e_core.console.app import handle
from i2e_core.console.views.intent import render_intent_detail
from i2e_core.console.views.pending import render_pending
from i2e_core.evidence import CurrentEvidence, ItemVerdict, write_current
from i2e_core.intent import Capability, EvidenceItem, Frontmatter, parse_intent, write_intent
from i2e_core.pending import PendingFile, read_pending, write_pending


def _seed_current(root: Path, slug: str) -> None:
    (root / ".i2e" / "evidence" / slug).mkdir(parents=True, exist_ok=True)
    write_current(
        root,
        CurrentEvidence(
            capability=slug,
            last_run="2026-05-21-aaa000",
            intent_version=1,
            items={
                f"{slug}-case": ItemVerdict(
                    verdict="pass",
                    attempts_used=1,
                    last_observed=datetime(2026, 5, 21, tzinfo=timezone.utc),
                )
            },
        ),
    )


def _seed_intent(root: Path, slug: str, status: str = "draft") -> Path:
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
        ),
        description=f"# {slug}\n\nA test capability.",
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


def _seed_pending(root: Path) -> Path:
    return write_pending(
        root,
        PendingFile(
            kind="human_evaluation",
            capability="demo-cap",
            item_id="demo-target",
            asked_at=datetime(2026, 5, 21, 14, 0, 0, tzinfo=timezone.utc),
            ask="Does the strip render?",
            expect="yes",
            verdict_options=["yes", "no", "partial"],
        ),
    )


# ── pending view ─────────────────────────────────────────────────────────────


def test_render_pending_empty(tmp_path):
    (tmp_path / ".i2e" / "pending").mkdir(parents=True)
    html = render_pending(tmp_path)
    assert 'id="pending-view"' in html
    assert "Inbox zero" in html


def test_render_pending_with_items(tmp_path):
    _seed_pending(tmp_path)
    html = render_pending(tmp_path)
    assert 'class="pending-card"' in html
    assert "demo-cap" in html
    assert 'hx-post="/api/pending/' in html
    assert "human-evaluations" in html


# ── router: GET ──────────────────────────────────────────────────────────────


def test_handle_get_pages(tmp_path):
    _seed_intent(tmp_path, "demo-cap", "active")
    for path in ("/", "/pending", "/workers", "/logs", "/logs?mode=table"):
        bare, _, qs = path.partition("?")
        resp = handle(tmp_path, "GET", bare, qs, "")
        assert resp.status == 200, path
        assert resp.content_type.startswith("text/html")
        assert b"<!doctype html>" in resp.body.lower()


def test_handle_get_intent_and_404(tmp_path):
    _seed_intent(tmp_path, "demo-cap", "active")
    ok = handle(tmp_path, "GET", "/intent/demo-cap", "", "")
    assert ok.status == 200
    assert b"demo-cap" in ok.body

    missing = handle(tmp_path, "GET", "/no/such/path", "", "")
    assert missing.status == 404


def test_handle_static_asset(tmp_path):
    css = handle(tmp_path, "GET", "/static/console.css", "", "")
    assert css.status == 200
    assert css.content_type == "text/css; charset=utf-8"
    assert b":root" in css.body

    blocked = handle(tmp_path, "GET", "/static/../serve.py", "", "")
    assert blocked.status == 404


# ── router: POST actions ─────────────────────────────────────────────────────


def test_handle_promote_valid(tmp_path):
    path = _seed_intent(tmp_path, "good-cap", "draft")
    resp = handle(tmp_path, "POST", "/api/intents/good-cap/promote", "", "")
    assert resp.status == 200
    assert b"promoted" in resp.body
    assert parse_intent(path).frontmatter.status == "active"


def test_handle_promote_invalid_retargets_modal(tmp_path):
    # A failed promote must surface as a full-screen modal: the response
    # retargets to the body-level #modal-mount instead of swapping inline
    # into the meta card's #status-result slot.
    resp = handle(tmp_path, "POST", "/api/intents/no-such-cap/promote", "", "")
    assert resp.status == 200
    assert resp.headers.get("HX-Retarget") == "#modal-mount"
    assert resp.headers.get("HX-Reswap") == "innerHTML"
    assert b'class="modal-overlay"' in resp.body
    assert b'role="dialog"' in resp.body


def test_intent_page_has_body_level_modal_mount(tmp_path):
    # The shell must carry a body-level mount point so a retargeted modal
    # lands as a direct child of <body> where position:fixed is reliable.
    _seed_intent(tmp_path, "demo-cap", "draft")
    resp = handle(tmp_path, "GET", "/intent/demo-cap", "", "")
    assert resp.status == 200
    assert b'id="modal-mount"' in resp.body


def test_handle_resolve_writes_block(tmp_path):
    pending_path = _seed_pending(tmp_path)
    resp = handle(
        tmp_path,
        "POST",
        f"/api/pending/{pending_path.name}/resolve",
        "",
        "verdict=yes&notes=looks+good",
    )
    assert resp.status == 200
    assert b"resolved" in resp.body
    updated = read_pending(pending_path)
    assert updated.status == "resolved"
    assert "yes" in (updated.resolution or "")


def test_handle_unknown_post_is_404(tmp_path):
    resp = handle(tmp_path, "POST", "/api/nope", "", "")
    assert resp.status == 404


# ── demote: un-started active intents only ───────────────────────────────────


def test_handle_demote_unstarted_active(tmp_path):
    path = _seed_intent(tmp_path, "fresh-cap", "active")
    resp = handle(tmp_path, "POST", "/api/intents/fresh-cap/demote", "", "")
    assert resp.status == 200
    assert b"demoted" in resp.body
    assert parse_intent(path).frontmatter.status == "draft"


def test_handle_demote_blocked_when_started(tmp_path):
    path = _seed_intent(tmp_path, "busy-cap", "active")
    _seed_current(tmp_path, "busy-cap")  # an evidence snapshot = started
    resp = handle(tmp_path, "POST", "/api/intents/busy-cap/demote", "", "")
    assert resp.status == 200
    assert b"Cannot demote" in resp.body
    # Status must NOT change — a started intent keeps its run history.
    assert parse_intent(path).frontmatter.status == "active"


def test_handle_demote_rejects_non_active(tmp_path):
    path = _seed_intent(tmp_path, "draft-cap", "draft")
    resp = handle(tmp_path, "POST", "/api/intents/draft-cap/demote", "", "")
    assert resp.status == 200
    assert b"Cannot demote" in resp.body
    assert parse_intent(path).frontmatter.status == "draft"


def test_intent_view_demote_button_state(tmp_path):
    # Un-started active → demote button enabled.
    _seed_intent(tmp_path, "fresh-cap", "active")
    html = render_intent_detail(tmp_path, "fresh-cap")
    assert 'id="demote-button"' in html
    idx = html.find('id="demote-button"')
    assert "disabled" not in html[idx:html.find(">", idx)]
    assert 'hx-post="/api/intents/fresh-cap/demote"' in html

    # Started active → demote button disabled.
    _seed_intent(tmp_path, "busy-cap", "active")
    _seed_current(tmp_path, "busy-cap")
    html2 = render_intent_detail(tmp_path, "busy-cap")
    idx2 = html2.find('id="demote-button"')
    assert "disabled" in html2[idx2:html2.find(">", idx2)]
