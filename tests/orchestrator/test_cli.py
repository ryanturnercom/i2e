"""CLI: ``python -m i2e_core.orchestrator`` exit-code contract."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from i2e_core.orchestrator import _main

from .conftest import FakeProvider, always_pass


def _basic_evidence() -> list[dict]:
    return [
        {
            "id": "case-a",
            "type": "case",
            "provider": "pytest",
            "query": "tests/test_a.py",
            "expect": "passes",
            "effort": "medium",
        }
    ]


def test_cli_exits_zero_on_shippable(
    project: Path, write_intent, write_current_for, patch_providers, capsys
):
    """Shippable tick → exit 0, JSON to stdout."""
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent("alpha", evidence=_basic_evidence(), version=1)
    write_current_for(
        "alpha",
        {"case-a": {"verdict": "pass", "attempts_used": 0}},
        intent_version=1,
    )
    rc = _main(["--root", str(project)])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    assert payload["shippable"] is True
    assert payload["actions_log"] == []


def test_cli_exits_one_on_preflight_failure(
    project: Path, write_intent, patch_providers, capsys
):
    """Bad intent → exit 1 + message on stderr."""
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent(
        "bad",
        evidence=[
            {
                "id": "x",
                "type": "case",
                "provider": "ghost",
                "query": "q",
                "expect": "p",
                "effort": "medium",
            }
        ],
        version=1,
    )
    rc = _main(["--root", str(project)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "preflight failed" in err
    assert "bad" in err


def test_cli_exits_two_on_unexpected_exception(
    project: Path, write_intent, patch_providers, monkeypatch
):
    """Unexpected exceptions propagate to exit code 2."""
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})
    write_intent("alpha", evidence=_basic_evidence(), version=1)

    def boom(root):
        raise RuntimeError("orchestrator detonated")

    monkeypatch.setattr("i2e_core.orchestrator.tick", boom)
    rc = _main(["--root", str(project)])
    assert rc == 2


def test_cli_subprocess_invocation(
    project: Path, write_intent, write_current_for, tmp_path: Path
):
    """End-to-end: invoke as ``python -m i2e_core.orchestrator`` via subprocess.

    Uses the real installed providers (none in a tmp project) — we just want
    to confirm the module entry point is wired correctly and emits exit 0 on
    a shippable state. We add a constraint that uses no provider lookup at
    the runner level by going straight to ``Shippable`` (current.yaml is
    pass).
    """
    # The real `installed_provider_names` returns the set installed under
    # ~/.claude/skills + project-local .claude/skills. The test project here
    # has no .claude/ dir, but the user's home directory might. We deliberately
    # pick a provider that won't fail validation regardless: an item with
    # provider=pytest is valid because the repo *does* ship an
    # `i2e-provider-pytest` skill. Since the state is Shippable, the runner
    # is never invoked.
    intents = project / ".i2e" / "intents"
    intents.mkdir(parents=True, exist_ok=True)
    (intents / "alpha.md").write_text(
        "---\n"
        "capability: alpha\n"
        "created: 2026-05-19\n"
        "updated: 2026-05-19\n"
        "version: 1\n"
        "status: active\n"
        "watcher: '@me'\n"
        "---\n\n"
        "# alpha\n\nDemo.\n\n"
        "## Evidence of success\n\n"
        "- id: case-a\n"
        "  type: case\n"
        "  provider: pytest\n"
        "  query: tests/test_a.py\n"
        "  expect: passes\n"
        "  effort: medium\n\n"
        "## Constraints\n\n",
        encoding="utf-8",
    )
    write_current_for(
        "alpha",
        {"case-a": {"verdict": "pass", "attempts_used": 0}},
        intent_version=1,
    )

    completed = subprocess.run(
        [sys.executable, "-m", "i2e_core.orchestrator", "--root", str(project)],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout.strip())
    assert payload["shippable"] is True
