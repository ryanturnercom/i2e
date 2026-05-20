"""CLI helper: `python -m i2e_core.evidence_runner <cap>`."""

from __future__ import annotations

import json
from pathlib import Path

from i2e_core.evidence_runner import _main

from .conftest import FakeProvider, always_pass


def test_cli_exits_zero_on_success(
    project: Path, write_intent, patch_providers, capsys
):
    write_intent(
        "demo",
        evidence=[
            {
                "id": "case-a",
                "type": "case",
                "provider": "pytest",
                "query": "tests/test_a.py",
                "expect": "passes",
            }
        ],
    )
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})

    rc = _main(["demo", "--root", str(project)])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    parsed = json.loads(out)
    assert parsed["pass"] == 1
    assert parsed["total"] == 1


def test_cli_exits_one_on_validation_failure(
    project: Path, write_intent, patch_providers, capsys
):
    write_intent(
        "demo",
        evidence=[
            {
                "id": "case-a",
                "type": "case",
                "provider": "nonexistent",
                "query": "x",
                "expect": "y",
            }
        ],
    )
    # Patch with only "pytest" — "nonexistent" is unknown.
    patch_providers({"pytest": FakeProvider("pytest", always_pass())})

    rc = _main(["demo", "--root", str(project)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "validation failed" in err
