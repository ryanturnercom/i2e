"""Scheduler integration helper — spec §6.3.

The orchestrator is BYO-scheduler. This helper offers a first-run experience:

- :func:`detect_claude_code` — is the ``claude`` CLI on PATH?
- :func:`suggest_registration` — a one-liner the operator can paste to register
  a Claude Code ``/schedule`` routine for ``python -m i2e_core.orchestrator``
- :func:`os_scheduler_templates` — copy-paste snippets for Windows Task
  Scheduler, macOS ``launchd``, and Linux ``cron``

We intentionally do NOT install schedulers — the helper only prints
suggestions. The operator decides what to run.

CLI: ``python -m i2e_core.scheduler suggest`` prints the suggestion + all
three OS templates.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from .config import load_config


# ---------- detection ----------


def detect_claude_code() -> bool:
    """Return True iff the ``claude`` CLI is on PATH."""
    return shutil.which("claude") is not None


# ---------- Claude Code /schedule suggestion ----------


def suggest_registration(root: Path, cadence: str | None = None) -> str:
    """Return a one-line ``claude /schedule`` command for the given project.

    The cadence defaults to the value from ``<root>/.i2e/config.yaml`` (which
    itself defaults to ``"weekly"``).
    """
    root = Path(root).resolve()
    if cadence is None:
        try:
            cfg = load_config(root)
            cadence = cfg.scheduler.cadence
        except Exception:
            cadence = "weekly"
    return (
        f'claude /schedule "Run i2e" '
        f'--cwd "{root}" '
        f"--cadence {cadence}"
    )


# ---------- OS-native scheduler templates ----------


_WINDOWS_TEMPLATE = """\
# Windows Task Scheduler — one-shot registration (PowerShell):
$action = New-ScheduledTaskAction `
    -Execute "{python}" `
    -Argument "-m i2e_core.orchestrator --root \\"{root}\\""
$trigger = New-ScheduledTaskTrigger -{cadence_flag} -At 09:00
Register-ScheduledTask -TaskName "i2e-{slug}" `
    -Action $action -Trigger $trigger -Description "I2E orchestrator tick"
"""


_LAUNCHD_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<!-- macOS launchd plist — save as ~/Library/LaunchAgents/com.i2e.{slug}.plist -->
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
                       "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>          <string>com.i2e.{slug}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{python}</string>
    <string>-m</string>
    <string>i2e_core.orchestrator</string>
    <string>--root</string>
    <string>{root}</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>   <integer>9</integer>
    <key>Minute</key> <integer>0</integer>
  </dict>
  <key>StandardErrorPath</key>  <string>{root}/.i2e/logs/scheduler.err</string>
  <key>StandardOutPath</key>    <string>{root}/.i2e/logs/scheduler.out</string>
</dict>
</plist>
"""


_CRON_TEMPLATE = """\
# Linux cron — append to ``crontab -e``. Adjust the cadence to taste.
# Default: 9am every day (use 'MM HH * * 1' for weekly on Mondays, etc.)
{cron_expr} cd "{root}" && {python} -m i2e_core.orchestrator --root "{root}" \\
    >> "{root}/.i2e/logs/scheduler.out" \\
    2>> "{root}/.i2e/logs/scheduler.err"
"""


_CADENCE_TO_CRON: dict[str, str] = {
    "hourly": "0 * * * *",
    "daily": "0 9 * * *",
    "weekly": "0 9 * * 1",
    "monthly": "0 9 1 * *",
}

_CADENCE_TO_WIN_FLAG: dict[str, str] = {
    "hourly": "Once -RepetitionInterval (New-TimeSpan -Hours 1)",
    "daily": "Daily",
    "weekly": "Weekly -DaysOfWeek Monday",
    "monthly": "Weekly -DaysOfWeek Monday -WeeksInterval 4",
}


def _cron_expr(cadence: str) -> str:
    return _CADENCE_TO_CRON.get(cadence, _CADENCE_TO_CRON["weekly"])


def _windows_cadence_flag(cadence: str) -> str:
    return _CADENCE_TO_WIN_FLAG.get(cadence, _CADENCE_TO_WIN_FLAG["weekly"])


def os_scheduler_templates(
    root: Path, cadence: str | None = None
) -> dict[str, str]:
    """Render the three OS scheduler templates for this project.

    Keys returned: ``"windows"``, ``"launchd"``, ``"cron"``. Each value is
    a fully rendered, copy-pastable snippet referencing this project's path
    and the current Python interpreter.
    """
    root = Path(root).resolve()
    if cadence is None:
        try:
            cfg = load_config(root)
            cadence = cfg.scheduler.cadence
        except Exception:
            cadence = "weekly"

    slug = root.name or "project"
    python = sys.executable or "python"

    return {
        "windows": _WINDOWS_TEMPLATE.format(
            python=python,
            root=str(root),
            slug=slug,
            cadence_flag=_windows_cadence_flag(cadence),
        ),
        "launchd": _LAUNCHD_TEMPLATE.format(
            python=python,
            root=str(root),
            slug=slug,
        ),
        "cron": _CRON_TEMPLATE.format(
            python=python,
            root=str(root),
            cron_expr=_cron_expr(cadence),
        ),
    }


# ---------- CLI ----------


def _print_section(title: str, body: str) -> None:
    print(f"\n# ===== {title} =====\n")
    print(body.rstrip())


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m i2e_core.scheduler",
        description="Print scheduling suggestions for the I2E orchestrator.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sug = sub.add_parser("suggest", help="Print Claude Code + OS templates.")
    sug.add_argument("--root", default=".", help="Project root (default cwd).")
    sug.add_argument("--cadence", default=None, help="Override cadence.")

    args = parser.parse_args(argv)
    root = Path(args.root)

    cc_present = detect_claude_code()
    print(f"# Claude Code CLI detected: {cc_present}")
    if cc_present:
        print("# Suggested registration:")
        print(suggest_registration(root, cadence=args.cadence))
    else:
        print("# (claude not on PATH — fall back to OS templates below)")

    templates = os_scheduler_templates(root, cadence=args.cadence)
    _print_section("Windows Task Scheduler", templates["windows"])
    _print_section("macOS launchd", templates["launchd"])
    _print_section("Linux cron", templates["cron"])
    return 0


if __name__ == "__main__":  # pragma: no cover - thin CLI shim
    raise SystemExit(_main(sys.argv[1:]))


__all__ = [
    "detect_claude_code",
    "os_scheduler_templates",
    "suggest_registration",
]
