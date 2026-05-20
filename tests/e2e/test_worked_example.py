"""End-to-end smoke test — the spec §10 password-validator worked example.

Scenario (mirrors the spec's narrative):

1. A user reports that ``"   "`` (three spaces) is accepted as a password.
2. The operator authors a ``change-password`` capability with three items:
   - ``short-password-rejected`` (case)   — minimum length must be enforced
   - ``whitespace-password-rejected`` (case) — pure-whitespace must be rejected
   - ``min-length-enforced`` (constraint) — explicit min-length boundary check
3. The repo ships a buggy ``src/change_password.py`` whose validator only
   checks ``len(p) > 0``. The first evidence run fails all three.
4. The "develop simulator" patches ``src/change_password.py`` to a correct
   validator. The next evidence run goes all-green.

The test exercises the **full IDEA loop**:

- **Intent**: ``i2e_core.intent_authoring.save`` writes the capability
- **Develop**: the simulator function (stands in for the LLM-driven skill)
- **Evidence**: real ``i2e_core.evidence_runner.run`` invocation, which
  invokes the real ``i2e-provider-pytest`` and shells out to pytest
- **Adapt**: ``i2e_core.adapt.plan`` reports the failures as retries
- **Report**: ``i2e_core.report.render`` writes ``.i2e/report.html`` with
  ``shippable=True`` after the second evidence run

Marked ``@pytest.mark.e2e`` so the default test invocation skips it.
"""

from __future__ import annotations

import shutil
import sys
import textwrap
from datetime import date
from pathlib import Path

import pytest

from i2e_core import adapt, evidence_runner
from i2e_core.evidence import read_current
from i2e_core.intent import Capability, Constraint, EvidenceItem, Frontmatter
from i2e_core.intent_authoring import save
from i2e_core.orchestrator import (
    DevelopAndEvidence,
    Shippable,
    decide,
    tick,
)
from i2e_core.report import render


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REAL_SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"


# ---------- staged source code ----------


_BUGGY_VALIDATOR = '''\
"""change_password — the buggy validator from spec §10.

This version accepts anything with at least one character — including
``"   "`` (three spaces) — which is exactly the user-reported bug.
"""


def is_valid_password(password: str) -> bool:
    return len(password) > 0
'''


_FIXED_VALIDATOR = '''\
"""change_password — the corrected validator.

Rejects:

- empty / whitespace-only strings
- any password shorter than ``MIN_LENGTH``
"""


MIN_LENGTH = 8


def is_valid_password(password: str) -> bool:
    if not isinstance(password, str):
        return False
    if not password.strip():
        return False
    if len(password) < MIN_LENGTH:
        return False
    return True
'''


# Project conftest.py — adds ``src/`` to sys.path so pytest subprocesses can
# import ``change_password`` from anywhere under the project tree.
_PROJECT_CONFTEST = '''\
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SRC = _HERE / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
'''


# Three test files mirroring the spec's structure.

_TEST_SHORT = '''\
import pytest
from change_password import is_valid_password


def test_short_password_rejected():
    """A 3-character password must be rejected (min length boundary)."""
    assert is_valid_password("abc") is False
'''


_TEST_WHITESPACE = '''\
import pytest
from change_password import is_valid_password


def test_whitespace_password_rejected():
    """The user-reported bug — ``"   "`` must not be accepted."""
    assert is_valid_password("   ") is False
'''


_TEST_CONSTRAINT = '''\
import pytest
from change_password import is_valid_password, MIN_LENGTH


def test_password_min_length():
    """Constraint: the published min length must reject anything shorter."""
    short = "a" * (MIN_LENGTH - 1)
    long_ok = "a" * MIN_LENGTH
    assert is_valid_password(short) is False
    assert is_valid_password(long_ok) is True
'''


# ---------- helpers ----------


def _stage_project(root: Path) -> None:
    """Build the project skeleton under ``root``."""
    for sub in ("context", "intents", "evidence", "pending", "logs"):
        (root / ".i2e" / sub).mkdir(parents=True, exist_ok=True)

    # src/change_password.py — buggy version
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "change_password.py").write_text(
        _BUGGY_VALIDATOR, encoding="utf-8"
    )

    # Project conftest so pytest subprocesses can import from src/.
    (root / "conftest.py").write_text(_PROJECT_CONFTEST, encoding="utf-8")

    # Three test files at the spec's paths.
    edge = root / "tests" / "edge"
    adv = root / "tests" / "adversarial"
    const = root / "tests" / "constraints"
    for d in (edge, adv, const):
        d.mkdir(parents=True, exist_ok=True)
    (edge / "test_short_password_rejected.py").write_text(
        _TEST_SHORT, encoding="utf-8"
    )
    (adv / "test_whitespace_password_rejected.py").write_text(
        _TEST_WHITESPACE, encoding="utf-8"
    )
    (const / "test_password_min_length.py").write_text(
        _TEST_CONSTRAINT, encoding="utf-8"
    )

    # Install the pytest provider skill into the project's .claude/skills/
    # so discovery picks it up regardless of cwd.
    project_skills = root / ".claude" / "skills"
    project_skills.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        REAL_SKILLS_DIR / "i2e-provider-pytest",
        project_skills / "i2e-provider-pytest",
    )


def _build_capability() -> Capability:
    today = date.today()
    fm = Frontmatter(
        capability="change-password",
        created=today,
        updated=today,
        version=1,
        status="active",
        watcher="@me",
    )
    return Capability(
        frontmatter=fm,
        description=(
            "# change-password\n\n"
            "Enforce password validity: reject empty/whitespace, "
            "require minimum length."
        ),
        evidence=[
            EvidenceItem(
                id="short-password-rejected",
                type="case",
                provider="pytest",
                query=(
                    "tests/edge/test_short_password_rejected.py"
                    "::test_short_password_rejected"
                ),
                expect="passes",
                effort="medium",
            ),
            EvidenceItem(
                id="whitespace-password-rejected",
                type="case",
                provider="pytest",
                query=(
                    "tests/adversarial/test_whitespace_password_rejected.py"
                    "::test_whitespace_password_rejected"
                ),
                expect="passes",
                effort="medium",
            ),
        ],
        constraints=[
            Constraint(
                id="min-length-enforced",
                provider="pytest",
                query=(
                    "tests/constraints/test_password_min_length.py"
                    "::test_password_min_length"
                ),
                expect="passes",
                effort="medium",
            ),
        ],
    )


def _develop_simulator(root: Path) -> None:
    """Stand-in for the LLM-driven develop step: patch the buggy validator."""
    (root / "src" / "change_password.py").write_text(
        _FIXED_VALIDATOR, encoding="utf-8"
    )


def _all_green(root: Path, capability: str) -> bool:
    cur = read_current(root, capability)
    if cur is None or not cur.items:
        return False
    return all(v.verdict in {"pass", "met"} for v in cur.items.values())


# ---------- the test ----------


@pytest.mark.e2e
def test_worked_example_full_loop(tmp_path: Path) -> None:
    _stage_project(tmp_path)

    # ---------- Intent ----------
    cap = _build_capability()
    save(tmp_path, cap)
    intent_path = tmp_path / ".i2e" / "intents" / "change-password.md"
    assert intent_path.exists()

    # ---------- Tick 1: orchestrator picks DevelopAndEvidence ----------
    # (At this point no current.yaml → branch 2.)
    action = decide(tmp_path)
    assert isinstance(action, DevelopAndEvidence)
    assert action.capability == "change-password"

    result1 = tick(tmp_path)
    assert isinstance(result1.action, DevelopAndEvidence)
    assert result1.shippable is False
    assert any(a.startswith("ran_develop:") for a in result1.actions_log)
    assert any(a.startswith("ran_evidence:") for a in result1.actions_log)
    assert result1.report_path is not None
    assert result1.report_path.exists()

    # Evidence should have run; every item must currently be failing because
    # the validator still accepts whitespace + short passwords.
    cur1 = read_current(tmp_path, "change-password")
    assert cur1 is not None
    assert len(cur1.items) == 3
    failing = {iid for iid, v in cur1.items.items() if v.verdict == "fail"}
    assert failing == {
        "short-password-rejected",
        "whitespace-password-rejected",
        "min-length-enforced",
    }
    # The bug case is present in current.items, as the spec calls out.
    assert "whitespace-password-rejected" in cur1.items

    # ---------- Adapt: failing items have retry budget ----------
    plan = adapt.plan(tmp_path, "change-password")
    retry_ids = {b.item_id for b in plan.retries}
    assert retry_ids == {
        "short-password-rejected",
        "whitespace-password-rejected",
        "min-length-enforced",
    }
    assert plan.escalations == []

    # ---------- Develop simulator: patch the validator ----------
    _develop_simulator(tmp_path)

    # ---------- Tick 2: re-run evidence directly (LLM has just developed) ----------
    summary2 = evidence_runner.run(tmp_path, "change-password")
    assert summary2.fail == 0
    assert summary2.pass_ == 3  # all three items reported a Case "pass"

    cur2 = read_current(tmp_path, "change-password")
    assert cur2 is not None
    assert _all_green(tmp_path, "change-password")

    # ---------- Decide should now be Shippable ----------
    final_action = decide(tmp_path)
    assert isinstance(final_action, Shippable)

    # ---------- Report: shippable=True ----------
    report_path = render(tmp_path)
    assert report_path.exists()
    html = report_path.read_text(encoding="utf-8")
    assert "shippable" in html.lower()
    # Re-build the view model directly to assert structurally.
    from i2e_core.report import build_view_model

    vm = build_view_model(tmp_path)
    assert vm.shippable is True
    cap_view = next(c for c in vm.capabilities if c.slug == "change-password")
    assert {it.id for it in cap_view.items} == {
        "short-password-rejected",
        "whitespace-password-rejected",
        "min-length-enforced",
    }
    assert all(it.verdict in {"pass", "met"} for it in cap_view.items)
