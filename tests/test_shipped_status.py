"""Tests for the ``shipped`` capability state (intent-shipped-status).

Covers the auto-promote / auto-demote carve-out in the orchestrator, the
branch-2/3 skip vs branch-4 still-fires behaviour, manual flip via
``set_intent_status``, the Shipped section in the rendered report, and
spec documentation. Two constraint tests at the bottom enforce that
draft/active/retired semantics are preserved and that the orchestrator's
status writes only happen in the shipped-transition code paths.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import pytest

from i2e_core.evidence import CurrentEvidence, ItemVerdict, write_current
from i2e_core.intent import parse_intent
from i2e_core.intent_authoring import (
    _STATUS_ORDER,
    demote_intent,
    promote_intent,
    set_intent_status,
)
from i2e_core.orchestrator import (
    AdaptThenRetry,
    DevelopAndEvidence,
    ReEvaluateItem,
    Shippable,
    decide,
    tick,
)
from i2e_core.provider import (
    CaseResult,
    ProviderContext,
    ProviderResult,
    TargetResult,
)
from i2e_core.report import render_to_string


# ---------- Self-contained test helpers ----------


@dataclass
class FakeProvider:
    name: str
    behavior: Callable[[object, ProviderContext], ProviderResult]

    def invoke(self, item, ctx: ProviderContext) -> ProviderResult:
        return self.behavior(item, ctx)


def _pass_provider() -> FakeProvider:
    return FakeProvider(
        "pytest",
        lambda item, ctx: CaseResult(verdict="pass", output="ok"),
    )


def _fail_provider() -> FakeProvider:
    return FakeProvider(
        "pytest",
        lambda item, ctx: CaseResult(verdict="fail", output="boom"),
    )


def _target_met_provider() -> FakeProvider:
    return FakeProvider(
        "datadog",
        lambda item, ctx: TargetResult(
            value="ok", met="met", observed_at=datetime.now(timezone.utc)
        ),
    )


def _target_unmet_provider() -> FakeProvider:
    return FakeProvider(
        "datadog",
        lambda item, ctx: TargetResult(
            value="bad", met="unmet", observed_at=datetime.now(timezone.utc)
        ),
    )


def _seed_skeleton(root: Path) -> None:
    for sub in ("intents", "evidence", "pending", "logs", "context"):
        (root / ".i2e" / sub).mkdir(parents=True, exist_ok=True)


def _write_intent(
    root: Path,
    slug: str,
    *,
    status: str = "active",
    version: int = 1,
    evidence: list[dict] | None = None,
    constraints: list[dict] | None = None,
) -> Path:
    _seed_skeleton(root)
    ev_block: list[str] = []
    for ev in evidence or []:
        first = True
        for k, v in ev.items():
            ev_block.append(("- " if first else "  ") + f"{k}: {v}")
            first = False
        ev_block.append("")
    cn_block: list[str] = []
    for cn in constraints or []:
        first = True
        for k, v in cn.items():
            cn_block.append(("- " if first else "  ") + f"{k}: {v}")
            first = False
        cn_block.append("")
    body = (
        f"---\n"
        f"capability: {slug}\n"
        f"created: '2026-05-20'\n"
        f"updated: '2026-05-20'\n"
        f"version: {version}\n"
        f"status: {status}\n"
        f"watcher: '@me'\n"
        f"---\n\n"
        f"# {slug}\n\n"
        f"## Evidence of success\n\n"
        + "\n".join(ev_block).rstrip()
        + "\n\n## Constraints\n\n"
        + "\n".join(cn_block).rstrip()
        + "\n"
    )
    target = root / ".i2e" / "intents" / f"{slug}.md"
    target.write_text(body, encoding="utf-8")
    return target


def _write_current(
    root: Path,
    slug: str,
    items: dict[str, dict],
    intent_version: int = 1,
) -> Path:
    item_models: dict[str, ItemVerdict] = {}
    for item_id, payload in items.items():
        item_models[item_id] = ItemVerdict(
            verdict=payload["verdict"],
            value=payload.get("value"),
            attempts_used=payload.get("attempts_used", 0),
            last_observed=payload.get(
                "last_observed", datetime.now(timezone.utc)
            ),
            pending=payload.get("pending"),
            raw=payload.get("raw", {}),
        )
    return write_current(
        root,
        CurrentEvidence(
            capability=slug,
            last_run="2026-05-20-aaa000",
            intent_version=intent_version,
            items=item_models,
        ),
    )


def _patch_providers(
    monkeypatch: pytest.MonkeyPatch,
    providers: dict[str, FakeProvider],
) -> None:
    names = set(providers.keys())

    def _load(name: str, extra_paths=None):
        if name not in providers:
            raise LookupError(name)
        return providers[name]

    def _names(extra_paths=None) -> set[str]:
        return set(names)

    monkeypatch.setattr("i2e_core.evidence_runner.load_provider", _load)
    monkeypatch.setattr(
        "i2e_core.evidence_runner.installed_provider_names", _names
    )
    monkeypatch.setattr(
        "i2e_core.orchestrator.installed_provider_names", _names
    )


_CASE = {
    "id": "case-a",
    "type": "case",
    "provider": "pytest",
    "query": "tests/test_a.py",
    "expect": "passes",
    "effort": "medium",
}


def _target_with_window(window: str) -> dict:
    return {
        "id": "metric-a",
        "type": "target",
        "provider": "datadog",
        "query": "some_metric",
        "expect": "<100ms",
        "window": window,
        "effort": "medium",
    }


# ---------- Evidence tests ----------


def test_capability_auto_promotes_when_all_verdicts_pass_or_met(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_providers(monkeypatch, {"pytest": _pass_provider()})
    _write_intent(tmp_path, "alpha", evidence=[_CASE])
    monkeypatch.setattr("i2e_core.orchestrator.render", lambda root: None)

    result = tick(tmp_path)

    assert any(
        a.startswith("promoted_to_shipped: alpha") for a in result.actions_log
    ), result.actions_log
    cap = parse_intent(tmp_path / ".i2e" / "intents" / "alpha.md")
    assert cap.frontmatter.status == "shipped"


def test_capability_stays_active_with_any_non_green_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_b = {**_CASE, "id": "case-b", "query": "tests/test_b.py"}
    _patch_providers(
        monkeypatch,
        {
            "pytest": FakeProvider(
                "pytest",
                lambda item, ctx: (
                    CaseResult(verdict="pass", output="ok")
                    if item.id == "case-a"
                    else CaseResult(verdict="fail", output="boom")
                ),
            )
        },
    )
    _write_intent(tmp_path, "alpha", evidence=[_CASE, case_b])
    monkeypatch.setattr("i2e_core.orchestrator.render", lambda root: None)

    result = tick(tmp_path)

    assert not any(
        a.startswith("promoted_to_shipped") for a in result.actions_log
    ), result.actions_log
    cap = parse_intent(tmp_path / ".i2e" / "intents" / "alpha.md")
    assert cap.frontmatter.status == "active"


def test_branch2_does_not_pick_shipped_capability_for_develop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_providers(monkeypatch, {"pytest": _pass_provider()})
    # Shipped at v2 but no current.yaml → would be "scoped" for develop
    # if it were active. With status=shipped, branch 2 must skip it.
    _write_intent(tmp_path, "alpha", status="shipped", version=2, evidence=[_CASE])

    action = decide(tmp_path)
    assert isinstance(action, Shippable), action


def test_branch3_does_not_pick_shipped_capability_for_adapt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_providers(monkeypatch, {"pytest": _pass_provider()})
    # A trending verdict on an active capability with attempts left would
    # normally trigger AdaptThenRetry. As shipped, branch 3 must skip it.
    _write_intent(
        tmp_path,
        "alpha",
        status="shipped",
        evidence=[
            {
                **_CASE,
                "type": "target",
                "provider": "datadog",
                "expect": "<100ms",
            }
        ],
    )
    _write_current(
        tmp_path,
        "alpha",
        {"case-a": {"verdict": "trending", "attempts_used": 0, "value": "bad"}},
    )

    action = decide(tmp_path)
    assert not isinstance(action, AdaptThenRetry), action


def test_branch4_target_window_still_fires_for_shipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_providers(monkeypatch, {"datadog": _target_met_provider()})
    _write_intent(
        tmp_path,
        "alpha",
        status="shipped",
        evidence=[_target_with_window("5m")],
    )
    # last_observed in the past beyond the 5m window → branch 4 fires.
    past = datetime.now(timezone.utc) - timedelta(minutes=30)
    _write_current(
        tmp_path,
        "alpha",
        {"metric-a": {"verdict": "met", "last_observed": past, "value": "ok"}},
    )

    action = decide(tmp_path)
    assert isinstance(action, ReEvaluateItem), action
    assert action.capability == "alpha"
    assert action.item_id == "metric-a"


def test_target_regression_demotes_shipped_to_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_providers(monkeypatch, {"datadog": _target_unmet_provider()})
    _write_intent(
        tmp_path,
        "alpha",
        status="shipped",
        evidence=[_target_with_window("5m")],
    )
    past = datetime.now(timezone.utc) - timedelta(minutes=30)
    _write_current(
        tmp_path,
        "alpha",
        {"metric-a": {"verdict": "met", "last_observed": past, "value": "ok"}},
    )
    monkeypatch.setattr("i2e_core.orchestrator.render", lambda root: None)

    result = tick(tmp_path)

    assert any(
        a.startswith("demoted_to_active: alpha") for a in result.actions_log
    ), result.actions_log
    cap = parse_intent(tmp_path / ".i2e" / "intents" / "alpha.md")
    assert cap.frontmatter.status == "active"


def test_i2e_intent_can_flip_shipped_to_active(tmp_path: Path) -> None:
    _write_intent(tmp_path, "alpha", status="shipped", evidence=[_CASE])
    set_intent_status(tmp_path, "alpha", "active")
    cap = parse_intent(tmp_path / ".i2e" / "intents" / "alpha.md")
    assert cap.frontmatter.status == "active"


def test_report_renders_shipped_capabilities_in_their_own_section(
    tmp_path: Path,
) -> None:
    _write_intent(tmp_path, "alpha", status="shipped", evidence=[_CASE])
    _write_intent(tmp_path, "beta", status="active", evidence=[_CASE])
    _write_current(
        tmp_path, "alpha", {"case-a": {"verdict": "pass"}}
    )

    html = render_to_string(tmp_path)

    assert "Shipped (1)" in html
    assert 'id="shipped/alpha"' in html
    # Active card must still render in its own section under id=cap/...
    assert 'id="cap/beta"' in html
    # The shipped section sits under the Intent stage heading, not Active.
    assert "shipped-heading" in html


def test_spec_documents_shipped_state_in_2_1_and_6_1() -> None:
    spec = (
        Path(__file__).resolve().parent.parent
        / ".documentation"
        / "I2E_simplified.md"
    ).read_text(encoding="utf-8")
    # § 2.1 must list shipped in the status enum.
    body_21 = _section_body(spec, r"2\.1")
    assert "shipped" in body_21.lower()
    # § 6.1 must describe shipped semantics (auto-promote / auto-demote /
    # branch skipping).
    body_61 = _section_body(spec, r"6\.1")
    assert "shipped" in body_61.lower()


def _section_body(spec: str, section_num_re: str) -> str:
    """Return the body of ``### <num> ...`` up to the next ``## `` or ``### ``."""
    pattern = re.compile(
        rf"^(?:###?)\s+{section_num_re}\b.*?$",
        re.MULTILINE,
    )
    m = pattern.search(spec)
    if not m:
        return ""
    start = m.end()
    end = len(spec)
    next_section = re.search(r"^(?:###?)\s+\S+", spec[start:], re.MULTILINE)
    if next_section:
        end = start + next_section.start()
    return spec[start:end]


# ---------- Constraint tests ----------


def test_draft_active_retired_behavior_unchanged(tmp_path: Path) -> None:
    """Legacy three-state promote/demote ladder is preserved verbatim.

    Adding ``shipped`` must not shift the existing draft → active →
    retired transitions exercised by the report's Promote / Demote
    buttons (intent-status-controls-in-the-report).
    """
    assert _STATUS_ORDER == ("draft", "active", "retired")

    _write_intent(tmp_path, "alpha", status="draft", evidence=[_CASE])
    _write_intent(tmp_path, "bravo", status="active", evidence=[_CASE])
    _write_intent(tmp_path, "charlie", status="retired", evidence=[_CASE])

    assert promote_intent(tmp_path, "alpha") == ("draft", "active")
    assert promote_intent(tmp_path, "bravo") == ("active", "retired")
    assert demote_intent(tmp_path, "charlie") == ("retired", "active")
    set_intent_status(tmp_path, "alpha", "draft")
    with pytest.raises(ValueError):
        demote_intent(tmp_path, "alpha")
    with pytest.raises(ValueError):
        promote_intent(tmp_path, "bravo")  # bravo is now retired


def test_orchestrator_status_carve_out_scoped_to_shipped_transitions() -> None:
    """Orchestrator's status writes must be confined to the shipped
    promote/demote carve-out — every other status edit goes through
    ``i2e-intent`` / ``intent_authoring`` directly (spec §6.1).
    """
    src = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "i2e_core"
        / "orchestrator.py"
    ).read_text(encoding="utf-8")
    # Only the two carve-out functions may import or call set_intent_status.
    matches = re.findall(r"set_intent_status\(", src)
    assert matches, "orchestrator must call set_intent_status from its carve-out"
    # Each call must live inside one of the named carve-out helpers, never
    # at module scope or inside other code paths.
    for fn_name in (
        "_orchestrator_promote_to_shipped",
        "_orchestrator_demote_to_active",
    ):
        body = _function_body(src, fn_name)
        assert "set_intent_status(" in body, (
            f"{fn_name} must call set_intent_status"
        )
    # Top-level body of tick(): no direct set_intent_status calls.
    tick_body = _function_body(src, "tick")
    assert "set_intent_status(" not in tick_body, (
        "tick() must go through the carve-out helpers, not set_intent_status"
    )


def _function_body(src: str, name: str) -> str:
    """Return the body of ``def <name>(...):`` until the next top-level def."""
    pattern = re.compile(rf"^def {re.escape(name)}\b", re.MULTILINE)
    m = pattern.search(src)
    if not m:
        return ""
    start = m.start()
    next_def = re.search(r"^def \w", src[start + 1 :], re.MULTILINE)
    if next_def:
        return src[start : start + 1 + next_def.start()]
    return src[start:]
