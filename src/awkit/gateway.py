"""Single boundary for subprocess and HTTP calls.

Every call this tool makes to an external program (or over HTTP) goes through this
module, so tests can substitute fakes in one place (design guide section 14).
Commands are always run as argv lists, never through a shell.
"""

from __future__ import annotations

import subprocess


def run(
    argv: list[str],
    *,
    stdin: str | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run ``argv`` without a shell and capture its text output."""
    return subprocess.run(
        argv,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
