"""Friendly cron-job setup for automatic sync (the ``zotrm cron`` command).

The interactive parts use questionary; the schedule/cron-line building and the
crontab merge logic are kept as plain functions so they are easy to test.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import questionary

from zotrm.config import DEFAULT_CONFIG, die, log

MARKER = "# zotrm-sync"

# Friendly label -> fixed cron expression (None means "needs follow-up questions").
PRESETS: dict[str, str | None] = {
    "Every hour": "0 * * * *",
    "Every 6 hours": "0 */6 * * *",
    "Once a day": None,
    "Once a week": None,
    "Advanced (cron expression)": None,
}

_WEEKDAYS = [
    ("Monday", 1),
    ("Tuesday", 2),
    ("Wednesday", 3),
    ("Thursday", 4),
    ("Friday", 5),
    ("Saturday", 6),
    ("Sunday", 0),
]

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
_CRON_RE = re.compile(r"^\S+(\s+\S+){4}$")


def build_schedule(
    preset: str,
    *,
    time: str | None = None,
    weekday: int | None = None,
    custom: str | None = None,
) -> str:
    """Turn a friendly choice into a 5-field cron expression."""
    fixed = PRESETS.get(preset)
    if fixed is not None:
        return fixed
    if preset == "Advanced (cron expression)":
        if not custom or not _CRON_RE.match(custom.strip()):
            die(f"invalid cron expression: {custom!r}")
        return custom.strip()
    if time is None or not _TIME_RE.match(time):
        die(f"invalid time (expected HH:MM): {time!r}")
    hour, minute = (int(part) for part in time.split(":"))
    if preset == "Once a day":
        return f"{minute} {hour} * * *"
    if preset == "Once a week":
        return f"{minute} {hour} * * {weekday}"
    die(f"unknown schedule: {preset!r}")


def zotrm_command(config_path: Path) -> str:
    """Build the absolute command cron should run."""
    exe = shutil.which("zotrm")
    parts = [exe] if exe else [sys.executable, "-m", "zotrm"]
    if config_path != DEFAULT_CONFIG:
        parts += ["--config", str(config_path)]
    parts.append("sync")
    return " ".join(parts)


def build_cron_line(schedule: str, command: str, logfile: str) -> str:
    return f"{schedule} {command} >> {logfile} 2>&1  {MARKER}"


def _crontab(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["crontab", *args],
            input=stdin,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        die("crontab not found on PATH; this command needs cron (macOS/Linux).")


def _read_crontab() -> list[str]:
    res = _crontab("-l")
    if res.returncode != 0:  # no crontab installed yet
        return []
    return res.stdout.splitlines()


def _write_crontab(lines: list[str]) -> None:
    res = _crontab("-", stdin="\n".join(lines) + "\n")
    if res.returncode != 0:
        die(f"could not write crontab: {res.stderr.strip()}")


def _without_marker(lines: list[str]) -> list[str]:
    return [line for line in lines if MARKER not in line]


def install_cron_line(line: str) -> None:
    """Add our cron line, replacing any previous zotrm-sync line."""
    lines = _without_marker(_read_crontab())
    lines.append(line)
    _write_crontab(lines)


def remove_cron_job() -> bool:
    """Remove our cron line. Returns True if one was present."""
    lines = _read_crontab()
    kept = _without_marker(lines)
    if len(kept) == len(lines):
        return False
    _write_crontab(kept)
    return True


def show_cron_job() -> str | None:
    for line in _read_crontab():
        if MARKER in line:
            return line
    return None


def _ask(question: Any) -> Any:
    answer = question.ask()
    if answer is None:
        die("cancelled")
    return answer


def run_cron_setup(config_path: Path) -> None:
    """Interactively schedule an automatic ``zotrm sync`` via cron."""
    if not config_path.exists():
        log(f"No config at {config_path}. Run 'zotrm config' first.")
        return

    preset = str(_ask(questionary.select("How often should it sync?", choices=list(PRESETS))))

    time: str | None = None
    weekday: int | None = None
    custom: str | None = None
    if preset == "Once a day":
        time = str(_ask(questionary.text("What time? (24h, e.g. 07:30)", default="07:00")))
    elif preset == "Once a week":
        day = str(_ask(questionary.select("Which day?", choices=[name for name, _ in _WEEKDAYS])))
        weekday = dict(_WEEKDAYS)[day]
        time = str(_ask(questionary.text("What time? (24h, e.g. 07:30)", default="07:00")))
    elif preset == "Advanced (cron expression)":
        custom = str(_ask(questionary.text("Cron expression (5 fields)", default="*/30 * * * *")))

    schedule = build_schedule(preset, time=time, weekday=weekday, custom=custom)
    logfile = str(config_path.parent / "sync.log")
    line = build_cron_line(schedule, zotrm_command(config_path), logfile)

    log(f"\nThis line will be added to your crontab:\n\n  {line}\n")
    if not bool(_ask(questionary.confirm("Install it?", default=True))):
        log("Aborted; crontab unchanged.")
        return

    install_cron_line(line)
    log(f"  ✓ Scheduled. Logs will go to {logfile}")
    log("  Check it any time with 'crontab -l' or 'zotrm cron --show'.")
