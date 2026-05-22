"""Tests for the ``i2e-regression`` capability.

The skill re-runs case + constraint evidence for shipped (or active, or
all) capabilities. Targets stay out of scope. Failed verdicts demote
shipped capabilities back to active. Each run lands a YAML log entry
under ``.i2e/logs/regressions/<run_id>.yaml``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pytest

from i2e_core import i2e_regression
from i2e_core.evidence import CurrentEvidence, ItemVerdict, write_current
from i2e_core.intent import parse_intent
from i2e_core.provider import (
    CaseResult,
    ProviderContext,
    ProviderResult,
    TargetResult,
)


# ---------- Self-contained helpers ----------


@dataclass
class FakeProvider:
    name: str
    behavior: Callable[[object, ProviderContext], ProviderResult]
    calls: list[str]

    def invoke(self, item, ctx: ProviderContext) -> ProviderResult:
        self.calls.append(item.id)
        return self.behavior(item, ctx)


def _pass(item, ctx):
    return CaseResult(verdict="pass", output="ok")


def _fail(item, ctx):
    return CaseResult(verdict="fail", output="boom")


def _target_met(item, ctx):
    return TargetResult(
        value="ok", met="met", observed_at=datetime.now(timezone.utc)
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
    ev_lines: list[str] = []
    for ev in evidence or []:
        first = True
        for k, v in ev.items():
            ev_lines.append(("- " if first else "  ") + f"{k}: {v}")
            first = False
        ev_lines.append("")
    cn_lines: list[str] = []
    for cn in constraints or []:
        first = True
        for k, v in cn.items():
            cn_lines.append(("- " if first else "  ") + f"{k}: {v}")
            first = False
        cn_lines.append("")
    body = (
        f"---\ncapability: {slug}\ncreated: '2026-05-20'\n"
        f"updated: '2026-05-20'\nversion: {version}\nstatus: {status}\n"
        f"watcher: '@me'\n---\n\n"
        f"# {slug}\n\n## Evidence of success\n\n"
        + "\n".join(ev_lines).rstrip()
        + "\n\n## Constraints\n\n"
        + "\n".join(cn_lines).rstrip()
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
    for iid, payload in items.items():
        item_models[iid] = ItemVerdict(
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
    monkeypatch: pytest.MonkeyPatch, providers: dict[str, FakeProvider]
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


_CASE = {
    "id": "case-a",
    "type": "case",
    "provider": "pytest",
    "query": "tests/test_a.py",
    "expect": "passes",
    "effort": "medium",
}

_TARGET = {
    "id": "metric-a",
    "type": "target",
    "provider": "datadog",
    "query": "some_metric",
    "expect": "<100ms",
    "window": "5m",
    "effort": "medium",
}

_CONSTRAINT = {
    "id": "no-bad-stuff",
    "provider": "pytest",
    "query": "tests/test_constraint.py",
    "expect": "passes",
    "effort": "low",
}


# ---------- Cases ----------


def test_default_run_revalidates_all_shipped_capabilities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    _patch_providers(
        monkeypatch,
        {"pytest": FakeProvider("pytest", _pass, calls)},
    )
    _write_intent(tmp_path, "alpha", status="shipped", evidence=[_CASE])
    _write_intent(tmp_path, "bravo", status="shipped", evidence=[_CASE])
    _write_intent(tmp_path, "still-active", status="active", evidence=[_CASE])
    for slug in ("alpha", "bravo", "still-active"):
        _write_current(tmp_path, slug, {"case-a": {"verdict": "pass"}})

    result = i2e_regression.run(tmp_path)

    touched = {d.capability for d in result.capabilities}
    assert touched == {"alpha", "bravo"}
    # Each shipped capability had its single case re-run once.
    assert calls.count("case-a") == 2


def test_status_flag_filters_to_active_or_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    _patch_providers(
        monkeypatch,
        {"pytest": FakeProvider("pytest", _pass, calls)},
    )
    _write_intent(tmp_path, "alpha", status="shipped", evidence=[_CASE])
    _write_intent(tmp_path, "bravo", status="active", evidence=[_CASE])
    for slug in ("alpha", "bravo"):
        _write_current(tmp_path, slug, {"case-a": {"verdict": "pass"}})

    only_active = i2e_regression.run(tmp_path, status="active")
    assert {d.capability for d in only_active.capabilities} == {"bravo"}

    everything = i2e_regression.run(tmp_path, status="all")
    assert {d.capability for d in everything.capabilities} == {"alpha", "bravo"}


def test_capability_flag_scopes_to_single_slug(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    _patch_providers(
        monkeypatch,
        {"pytest": FakeProvider("pytest", _pass, calls)},
    )
    _write_intent(tmp_path, "alpha", status="shipped", evidence=[_CASE])
    _write_intent(tmp_path, "bravo", status="shipped", evidence=[_CASE])
    for slug in ("alpha", "bravo"):
        _write_current(tmp_path, slug, {"case-a": {"verdict": "pass"}})

    result = i2e_regression.run(tmp_path, capability="alpha")
    assert {d.capability for d in result.capabilities} == {"alpha"}


def test_case_failure_demotes_shipped_back_to_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    _patch_providers(
        monkeypatch,
        {"pytest": FakeProvider("pytest", _fail, calls)},
    )
    _write_intent(tmp_path, "alpha", status="shipped", evidence=[_CASE])
    _write_current(tmp_path, "alpha", {"case-a": {"verdict": "pass"}})

    result = i2e_regression.run(tmp_path)

    cap = parse_intent(tmp_path / ".i2e" / "intents" / "alpha.md")
    assert cap.frontmatter.status == "active"
    delta = result.capabilities[0]
    assert delta.demoted is True
    assert delta.new_status == "active"


def test_target_items_not_re_evaluated_by_regression(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_calls: list[str] = []
    target_calls: list[str] = []
    _patch_providers(
        monkeypatch,
        {
            "pytest": FakeProvider("pytest", _pass, case_calls),
            "datadog": FakeProvider("datadog", _target_met, target_calls),
        },
    )
    _write_intent(
        tmp_path,
        "alpha",
        status="shipped",
        evidence=[_CASE, _TARGET],
    )
    _write_current(
        tmp_path,
        "alpha",
        {
            "case-a": {"verdict": "pass"},
            "metric-a": {"verdict": "met", "value": "ok"},
        },
    )

    i2e_regression.run(tmp_path)

    assert case_calls == ["case-a"]
    assert target_calls == []  # target never invoked by regression


def test_run_writes_log_under_dot_i2e_logs_regressions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    _patch_providers(
        monkeypatch,
        {"pytest": FakeProvider("pytest", _pass, calls)},
    )
    _write_intent(tmp_path, "alpha", status="shipped", evidence=[_CASE])
    _write_current(tmp_path, "alpha", {"case-a": {"verdict": "pass"}})

    result = i2e_regression.run(tmp_path)

    log_dir = tmp_path / ".i2e" / "logs" / "regressions"
    assert log_dir.exists()
    files = list(log_dir.glob("*.yaml"))
    assert len(files) == 1
    assert files[0].name == f"{result.run_id}.yaml"
    text = files[0].read_text(encoding="utf-8")
    assert "alpha" in text
    assert result.run_id in text


def test_spec_documents_i2e_regression_in_4_1_and_appendix_b() -> None:
    spec = (
        Path(__file__).resolve().parent.parent
        / ".documentation"
        / "I2E_simplified.md"
    ).read_text(encoding="utf-8")
    # § 4.1 (loop skills) must list i2e-regression.
    sec_41 = _section_body(spec, r"4\.1")
    assert "i2e-regression" in sec_41
    # Appendix B (skill index) must list it too.
    appx_b = _appendix_body(spec, "B")
    assert "i2e-regression" in appx_b


# ---------- Constraints ----------


def test_target_verdicts_unchanged_by_regression(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A shipped capability with a target must keep its target verdict
    after a regression run — only cases + constraints get re-evaluated.
    """
    case_calls: list[str] = []
    _patch_providers(
        monkeypatch,
        {
            "pytest": FakeProvider("pytest", _pass, case_calls),
            "datadog": FakeProvider("datadog", _target_met, []),
        },
    )
    _write_intent(
        tmp_path,
        "alpha",
        status="shipped",
        evidence=[_CASE, _TARGET],
    )
    past = datetime.now(timezone.utc).replace(microsecond=0)
    _write_current(
        tmp_path,
        "alpha",
        {
            "case-a": {"verdict": "pass", "last_observed": past},
            "metric-a": {
                "verdict": "met",
                "value": "32ms",
                "last_observed": past,
            },
        },
    )

    i2e_regression.run(tmp_path)

    # Target verdict must be preserved verbatim.
    from i2e_core.evidence import read_current

    cur = read_current(tmp_path, "alpha")
    assert cur is not None
    assert cur.items["metric-a"].verdict == "met"
    assert cur.items["metric-a"].value == "32ms"


def test_draft_and_retired_capabilities_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    _patch_providers(
        monkeypatch,
        {"pytest": FakeProvider("pytest", _pass, calls)},
    )
    _write_intent(tmp_path, "draft-cap", status="draft", evidence=[_CASE])
    _write_intent(
        tmp_path, "retired-cap", status="retired", evidence=[_CASE]
    )
    _write_intent(tmp_path, "alpha", status="shipped", evidence=[_CASE])
    _write_current(tmp_path, "alpha", {"case-a": {"verdict": "pass"}})

    # status=all explicitly: still excludes draft + retired.
    result = i2e_regression.run(tmp_path, status="all")

    touched = {d.capability for d in result.capabilities}
    assert touched == {"alpha"}
    assert "draft-cap" not in touched
    assert "retired-cap" not in touched


# ---------- Helpers shared with shipped-status tests ----------


def _section_body(spec: str, section_num_re: str) -> str:
    pattern = re.compile(
        rf"^(?:###?)\s+{section_num_re}\b.*?$", re.MULTILINE
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


def _appendix_body(spec: str, letter: str) -> str:
    pattern = re.compile(
        rf"^##\s+Appendix\s+{letter}\b.*?$", re.MULTILINE
    )
    m = pattern.search(spec)
    if not m:
        return ""
    start = m.end()
    next_appendix = re.search(r"^##\s+Appendix\s+\S+", spec[start:], re.MULTILINE)
    if next_appendix:
        return spec[start : start + next_appendix.start()]
    return spec[start:]
