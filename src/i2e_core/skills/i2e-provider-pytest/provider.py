from __future__ import annotations

import subprocess
import sys

from i2e_core.provider import CaseResult, ProviderContext

_DEFAULT_TIMEOUT_S = 600


class PytestProvider:
    name = "pytest"

    def invoke(self, item, ctx: ProviderContext) -> CaseResult:
        cmd = [sys.executable, "-m", "pytest", item.query, "--no-header", "-q", "--tb=short"]
        try:
            result = subprocess.run(
                cmd,
                cwd=str(ctx.root),
                capture_output=True,
                text=True,
                timeout=_DEFAULT_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired as exc:
            tail = ""
            if exc.stdout:
                stdout = exc.stdout if isinstance(exc.stdout, str) else exc.stdout.decode("utf-8", "replace")
                tail = "\n".join(stdout.splitlines()[-40:])
            return CaseResult(
                verdict="fail",
                output=f"pytest timed out after {_DEFAULT_TIMEOUT_S}s for query {item.query!r}\n{tail}".rstrip(),
            )

        combined = (result.stdout or "") + (result.stderr or "")
        return CaseResult(
            verdict="pass" if result.returncode == 0 else "fail",
            output="\n".join(combined.splitlines()[-40:]),
        )


provider = PytestProvider()
