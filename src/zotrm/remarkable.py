"""Thin wrapper around the external ``rmapi`` binary (the ddvk fork).

``rmapi`` is a runtime system prerequisite, not a Python dependency. If it is
not on PATH we fail with a clear, actionable message instead of a traceback.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from zotrm.config import die

# Remote folders created this process; avoids redundant mkdir calls.
_MADE_FOLDERS: set[str] = set()

# Backoff delays (seconds) when reMarkable's auth endpoint returns HTTP 429.
_RETRY_DELAYS = (2.0, 5.0, 10.0)

# Common user/Homebrew bin directories missing from cron's minimal PATH (/usr/bin:/bin).
_EXTRA_BINS = (
    "/opt/homebrew/bin",
    "/usr/local/bin",
    str(Path.home() / ".local" / "bin"),
    str(Path.home() / "go" / "bin"),
)


def _run_rmapi(
    args: tuple[str, ...], capture: bool, cwd: str | None
) -> subprocess.CompletedProcess[str]:
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


def rmapi(
    *args: str, capture: bool = False, cwd: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Run an rmapi sub-command non-interactively, retrying on HTTP 429 rate limits."""
    entries = [*os.environ.get("PATH", "").split(os.pathsep), *_EXTRA_BINS]
    os.environ["PATH"] = os.pathsep.join(dict.fromkeys(entries)).strip(os.pathsep)
    res = _run_rmapi(args, capture, cwd)
    for delay in _RETRY_DELAYS:
        if res.returncode == 0 or "status 429" not in (res.stderr or ""):
            break
        time.sleep(delay)
        res = _run_rmapi(args, capture, cwd)
    return res


def ensure_remote_folder(folder: str, *, refresh: bool = False) -> None:
    """Create a (possibly nested) reMarkable folder, one level at a time."""
    if refresh:
        rmapi("refresh", capture=True)
        _MADE_FOLDERS.clear()
    path = ""
    for part in (p for p in folder.strip("/").split("/") if p):
        path = f"{path}/{part}"
        if path not in _MADE_FOLDERS:
            res = rmapi("mkdir", path, capture=True)
            if res.returncode == 0 or "already exists" in (res.stderr or ""):
                _MADE_FOLDERS.add(path)


def list_remote_files(folder: str) -> set[str]:
    """Return the set of full remote document paths under ``folder``."""
    res = rmapi("find", folder, capture=True)
    if res.returncode != 0:
        return set()
    return {
        "/" + line[4:].strip().lstrip("/")
        for line in res.stdout.splitlines()
        if line.startswith("[f] ")
    }
