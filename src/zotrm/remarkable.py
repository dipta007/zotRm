"""Thin wrapper around the external ``rmapi`` binary (the ddvk fork).

``rmapi`` is a runtime system prerequisite, not a Python dependency. If it is
not on PATH we fail with a clear, actionable message instead of a traceback.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from zotrm.config import die

# Remote folders created this process; avoids redundant mkdir calls.
_MADE_FOLDERS: set[str] = set()

# Common user/Homebrew bin directories missing from cron's minimal PATH (/usr/bin:/bin).
_EXTRA_BINS = (
    "/opt/homebrew/bin",
    "/usr/local/bin",
    str(Path.home() / ".local" / "bin"),
    str(Path.home() / "go" / "bin"),
)


def rmapi(
    *args: str, capture: bool = False, cwd: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Run an rmapi sub-command non-interactively (optionally in ``cwd``)."""
    entries = [*os.environ.get("PATH", "").split(os.pathsep), *_EXTRA_BINS]
    os.environ["PATH"] = os.pathsep.join(dict.fromkeys(entries)).strip(os.pathsep)
    try:
        return subprocess.run(
            ["rmapi", *args],
            check=False,
            text=True,
            capture_output=capture,
            cwd=cwd,
        )
    except FileNotFoundError:
        die("rmapi not found on PATH. Install the ddvk fork: brew install rmapi")


def ensure_remote_folder(folder: str, *, refresh: bool = False) -> None:
    """Create a (possibly nested) reMarkable folder, one level at a time."""
    if refresh:
        rmapi("refresh", capture=True)
        _MADE_FOLDERS.clear()
    path = ""
    for part in (p for p in folder.strip("/").split("/") if p):
        path = f"{path}/{part}"
        if path not in _MADE_FOLDERS:
            rmapi("mkdir", path, capture=True)  # harmless if it already exists
            _MADE_FOLDERS.add(path)
