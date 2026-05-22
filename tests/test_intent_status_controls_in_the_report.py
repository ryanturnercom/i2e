"""Promote / Demote intent status from the served experience.

Covers the deterministic mutators, the HTML control surface, and the
`POST /intent/status` endpoint that the buttons hit. All three together
satisfy the capability's Case.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from i2e_core.intent import parse_intent
from i2e_core.intent_authoring import (
    demote_intent,
    promote_intent,
    set_intent_status,
)
from i2e_core.report import render_to_string
from i2e_core.serve import start_server, stop_server


def _intent(name: str, status: str = "draft") -> str:
    nodeid = f"tests/test_{name.replace('-', '_')}.py::test_impl"
    return (
        f"---\n"
        f"capability: {name}\n"
        f"created: '2026-05-20'\n"
        f"updated: '2026-05-20'\n"
        f"version: 1\n"
        f"status: {status}\n"
        f"watcher: '@me'\n"
        f"---\n"
        f"\n"
        f"# {name}\n"
        f"\n"
        f"## Evidence of success\n"
        f"\n"
        f"- id: {name}-impl\n"
        f"  type: case\n"
        f"  provider: pytest\n"
        f"  query: {nodeid}\n"
        f"  expect: passes\n"
        f"  effort: medium\n"
        f"\n"
        f"## Constraints\n"
    )


def _seed(root: Path, slug: str, status: str) -> Path:
    for sub in ("intents", "evidence", "pending", "logs", "context"):
        (root / ".i2e" / sub).mkdir(parents=True, exist_ok=True)
    path = root / ".i2e" / "intents" / f"{slug}.md"
    path.write_text(_intent(slug, status), encoding="utf-8")
    return path


def _post_json(url: str, body: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        url,
        method="POST",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")


def test_implemented(tmp_path: Path) -> None:
    # --- 1. Deterministic mutators ------------------------------------------
    _seed(tmp_path, "alpha", "draft")
    _seed(tmp_path, "bravo", "active")
    _seed(tmp_path, "charlie", "retired")

    old, new = promote_intent(tmp_path, "alpha")
    assert (old, new) == ("draft", "active")
    assert parse_intent(tmp_path / ".i2e" / "intents" / "alpha.md").frontmatter.status == "active"

    old, new = promote_intent(tmp_path, "bravo")
    assert (old, new) == ("active", "retired")

    old, new = demote_intent(tmp_path, "charlie")
    assert (old, new) == ("retired", "active")

    # Edge: can't promote past retired or demote past draft.
    with pytest.raises(ValueError):
        promote_intent(tmp_path, "bravo")  # now retired
    set_intent_status(tmp_path, "alpha", "draft")
    with pytest.raises(ValueError):
        demote_intent(tmp_path, "alpha")

    # Edge: unknown slug.
    with pytest.raises(FileNotFoundError):
        set_intent_status(tmp_path, "nope", "active")

    # Edge: invalid status.
    with pytest.raises(ValueError):
        set_intent_status(tmp_path, "alpha", "bogus")  # type: ignore[arg-type]

    # Status set is idempotent — re-setting the same status is a no-op.
    set_intent_status(tmp_path, "alpha", "draft")
    assert parse_intent(tmp_path / ".i2e" / "intents" / "alpha.md").frontmatter.status == "draft"

    # Other frontmatter survives the mutation (version, watcher, evidence body).
    cap = parse_intent(tmp_path / ".i2e" / "intents" / "alpha.md")
    assert cap.frontmatter.version == 1
    assert cap.frontmatter.watcher == "@me"
    assert any(ev.id == "alpha-impl" for ev in cap.evidence)

    # --- 2. Report renders Promote / Demote buttons -------------------------
    # alpha is draft → rendered in the Drafts section, Demote disabled.
    # charlie is active → rendered in Capabilities, both buttons enabled.
    # (bravo is retired and hidden from the report — that's existing behavior.)
    html = render_to_string(tmp_path)
    assert 'class="status-controls"' in html
    assert 'data-slug="alpha"' in html
    assert 'data-slug="charlie"' in html
    # Retired intents are hidden — no card surfaces for bravo.
    assert 'data-slug="bravo"' not in html
    assert 'data-action="promote"' in html
    assert 'data-action="demote"' in html
    # Demote on a draft must be disabled in markup so the user can't click it.
    alpha_card = html.split('data-slug="alpha"', 1)[1].split("</section>", 1)[0]
    assert 'data-action="demote" disabled' in alpha_card
    # The handler script must live in the wrapper so live updates keep working.
    assert "/intent/status" in html

    # --- 3. POST /intent/status drives the mutator over HTTP ----------------
    try:
        url = start_server(tmp_path, port=0, open_browser=False).rstrip("/")
        # Give the watcher a moment to start so we don't race file events.
        time.sleep(0.05)

        # promote alpha: draft → active
        status, payload = _post_json(
            url + "/intent/status", {"slug": "alpha", "action": "promote"}
        )
        assert status == 200
        assert payload == {"slug": "alpha", "old": "draft", "new": "active"}
        assert (
            parse_intent(tmp_path / ".i2e" / "intents" / "alpha.md").frontmatter.status
            == "active"
        )

        # demote alpha back to draft
        status, payload = _post_json(
            url + "/intent/status", {"slug": "alpha", "action": "demote"}
        )
        assert status == 200
        assert payload["new"] == "draft"

        # set to explicit status
        status, payload = _post_json(
            url + "/intent/status",
            {"slug": "alpha", "action": "set", "status": "retired"},
        )
        assert status == 200
        assert (
            parse_intent(tmp_path / ".i2e" / "intents" / "alpha.md").frontmatter.status
            == "retired"
        )

        # Invalid action → 400 with an error payload.
        status, payload = _post_json(
            url + "/intent/status", {"slug": "alpha", "action": "bogus"}
        )
        assert status == 400
        assert "error" in payload

        # Unknown slug → 400.
        status, payload = _post_json(
            url + "/intent/status", {"slug": "no-such", "action": "promote"}
        )
        assert status == 400

        # Missing slug → 400.
        status, payload = _post_json(
            url + "/intent/status", {"action": "promote"}
        )
        assert status == 400
    finally:
        stop_server(tmp_path)
