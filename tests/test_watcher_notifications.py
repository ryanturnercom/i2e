"""Watcher notifications — land on the page and immediately see what needs you.

The surface aggregates failures, trending items, pending asks, and target
interventions, groups them by watcher, and renders deep-link rows so the
watcher can act in one click.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from i2e_core.evidence import CurrentEvidence, ItemVerdict, write_current
from i2e_core.pending import PendingFile, write_pending
from i2e_core.report import build_view_model, render_to_string


def _intent(name: str, watcher: str = "@me", *, with_target: bool = False) -> str:
    body = (
        f"---\n"
        f"capability: {name}\n"
        f"created: '2026-05-20'\n"
        f"updated: '2026-05-20'\n"
        f"version: 1\n"
        f"status: active\n"
        f"watcher: '{watcher}'\n"
        f"---\n"
        f"\n"
        f"## Evidence of success\n"
        f"\n"
        f"- id: {name}-case\n"
        f"  type: case\n"
        f"  provider: pytest\n"
        f"  query: q\n"
        f"  expect: passes\n"
        f"  effort: medium\n"
    )
    if with_target:
        body += (
            f"\n"
            f"- id: {name}-target\n"
            f"  type: target\n"
            f"  provider: human\n"
            f"  query: q\n"
            f"  expect: '>= 1'\n"
            f"  window: 7d\n"
            f"  effort: medium\n"
        )
    body += "\n## Constraints\n"
    return body


def _seed(root: Path) -> None:
    for sub in ("intents", "evidence", "pending", "logs", "context"):
        (root / ".i2e" / sub).mkdir(parents=True, exist_ok=True)


def _intent_path(root: Path, name: str) -> Path:
    return root / ".i2e" / "intents" / f"{name}.md"


def test_implemented(tmp_path: Path) -> None:
    _seed(tmp_path)

    # alpha: belongs to @alice, has a failing case + a target awaiting human
    _intent_path(tmp_path, "alpha").write_text(
        _intent("alpha", watcher="@alice", with_target=True), encoding="utf-8"
    )
    write_current(
        tmp_path,
        CurrentEvidence(
            capability="alpha",
            last_run="2026-05-20-aaa000",
            intent_version=1,
            items={
                "alpha-case": ItemVerdict(
                    verdict="fail",
                    value="boom",
                    attempts_used=1,
                    last_observed=datetime.now(timezone.utc),
                ),
                "alpha-target": ItemVerdict(
                    verdict="awaiting_human",
                    attempts_used=0,
                    last_observed=datetime.now(timezone.utc),
                    pending="alpha__alpha-target__pending.yaml",
                ),
            },
        ),
    )

    # bravo: belongs to @bob, has a trending target
    _intent_path(tmp_path, "bravo").write_text(
        _intent("bravo", watcher="@bob", with_target=True), encoding="utf-8"
    )
    write_current(
        tmp_path,
        CurrentEvidence(
            capability="bravo",
            last_run="2026-05-20-bbb000",
            intent_version=1,
            items={
                "bravo-case": ItemVerdict(
                    verdict="pass",
                    attempts_used=0,
                    last_observed=datetime.now(timezone.utc),
                ),
                "bravo-target": ItemVerdict(
                    verdict="trending",
                    value="0.8",
                    attempts_used=0,
                    last_observed=datetime.now(timezone.utc),
                ),
            },
        ),
    )

    # charlie: belongs to @alice, fully green — must not appear in notifications
    _intent_path(tmp_path, "charlie").write_text(
        _intent("charlie", watcher="@alice"), encoding="utf-8"
    )
    write_current(
        tmp_path,
        CurrentEvidence(
            capability="charlie",
            last_run="2026-05-20-ccc000",
            intent_version=1,
            items={
                "charlie-case": ItemVerdict(
                    verdict="pass",
                    attempts_used=0,
                    last_observed=datetime.now(timezone.utc),
                )
            },
        ),
    )

    # And an open pending file for alpha — adds a pending notification.
    write_pending(
        tmp_path,
        PendingFile(
            status="open",
            kind="human_evaluation",
            capability="alpha",
            item_id="alpha-case",
            asked_at=datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc),
            ask="Did the manual repro reproduce?",
            verdict_options=["yes", "no"],
        ),
    )

    # --- 1. View model rolls up exactly the items that need attention ------
    vm = build_view_model(tmp_path)
    kinds = sorted({n.kind for n in vm.notifications})
    assert "failure" in kinds
    assert "trending" in kinds
    assert "intervention" in kinds
    assert "pending" in kinds
    # Charlie (fully green) generates no notification.
    assert all(n.capability != "charlie" for n in vm.notifications)

    # Watchers preserved per source capability.
    by_cap = {(n.capability, n.item_id): n for n in vm.notifications}
    assert by_cap[("alpha", "alpha-case")].watcher == "@alice"
    assert by_cap[("bravo", "bravo-target")].watcher == "@bob"

    # Severity ordering: failures land first, then pending, then trending,
    # then intervention.
    kind_seq = [n.kind for n in vm.notifications]
    severity = {"failure": 0, "pending": 1, "trending": 2, "intervention": 3}
    assert kind_seq == sorted(kind_seq, key=lambda k: severity[k])

    # --- 2. HTML renders a notifications surface near the top --------------
    html = render_to_string(tmp_path)
    assert 'id="notifications"' in html
    # The banner shows up before the IDEA nav so the watcher sees it first.
    assert html.index('id="notifications"') < html.index('class="idea-nav"')
    assert "What needs you" in html

    # Each notification kind has a colored kind pill.
    assert "kind-failure" in html
    assert "kind-pending" in html
    assert "kind-trending" in html
    assert "kind-intervention" in html

    # Rows are deep-linked back to the underlying surfaces.
    assert 'href="#item/alpha/alpha-case"' in html
    assert 'href="#item/bravo/bravo-target"' in html
    # The pending notification links to the pending file by filename.
    assert "#pending/" in html

    # Watcher dividers group rows by who owns them.
    assert "watcher @alice" in html
    assert "watcher @bob" in html

    # --- 3. With no failures or pending, the banner is suppressed ----------
    _intent_path(tmp_path, "alpha").unlink()
    _intent_path(tmp_path, "bravo").unlink()
    # Drop the pending too.
    pending_dir = tmp_path / ".i2e" / "pending"
    for f in pending_dir.iterdir():
        f.unlink()

    vm2 = build_view_model(tmp_path)
    assert vm2.notifications == []
    html2 = render_to_string(tmp_path)
    assert 'id="notifications"' not in html2
