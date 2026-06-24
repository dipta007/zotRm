"""Cron helpers: schedule mapping, line building, and idempotent crontab merge."""

import subprocess

from zotrm.cron import (
    MARKER,
    build_cron_line,
    build_schedule,
    install_cron_line,
    remove_cron_job,
    show_cron_job,
)


def test_build_schedule_presets_and_followups():
    assert build_schedule("Every hour") == "0 * * * *"
    assert build_schedule("Every 6 hours") == "0 */6 * * *"
    assert build_schedule("Once a day", time="07:30") == "30 7 * * *"
    assert build_schedule("Once a week", time="09:05", weekday=1) == "5 9 * * 1"
    assert build_schedule("Advanced (cron expression)", custom="*/15 * * * *") == "*/15 * * * *"


def test_build_cron_line_has_command_log_and_marker():
    line = build_cron_line("0 * * * *", "/usr/local/bin/zotrm sync", "/home/u/sync.log")
    assert line.startswith("0 * * * * /usr/local/bin/zotrm sync")
    assert ">> /home/u/sync.log 2>&1" in line
    assert line.endswith(MARKER)


def _fake_crontab(state):
    """Return a subprocess.run stand-in backed by ``state['lines']``."""

    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["crontab", "-l"]:
            text = "\n".join(state["lines"])
            return subprocess.CompletedProcess(cmd, 0, stdout=text, stderr="")
        if cmd == ["crontab", "-"]:
            state["lines"] = kwargs["input"].strip().splitlines()
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    return fake_run


def test_install_replaces_existing_and_keeps_others(monkeypatch):
    state = {"lines": ["0 0 * * * backup-job", f"5 5 * * * old zotrm sync  {MARKER}"]}
    monkeypatch.setattr("zotrm.cron.subprocess.run", _fake_crontab(state))

    install_cron_line(f"0 * * * * zotrm sync  {MARKER}")

    markers = [line for line in state["lines"] if MARKER in line]
    assert len(markers) == 1  # replaced, not duplicated
    assert markers[0].startswith("0 * * * * zotrm sync")
    assert "0 0 * * * backup-job" in state["lines"]  # unrelated job preserved


def test_install_into_empty_crontab(monkeypatch):
    state = {"lines": []}

    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["crontab", "-l"]:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="no crontab")
        state["lines"] = kwargs["input"].strip().splitlines()
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("zotrm.cron.subprocess.run", fake_run)

    install_cron_line(f"0 * * * * zotrm sync  {MARKER}")
    assert state["lines"] == [f"0 * * * * zotrm sync  {MARKER}"]


def test_remove_and_show(monkeypatch):
    state = {"lines": ["0 0 * * * backup-job", f"0 * * * * zotrm sync  {MARKER}"]}
    monkeypatch.setattr("zotrm.cron.subprocess.run", _fake_crontab(state))

    assert show_cron_job() == f"0 * * * * zotrm sync  {MARKER}"
    assert remove_cron_job() is True
    assert state["lines"] == ["0 0 * * * backup-job"]
    assert remove_cron_job() is False  # nothing left to remove
    assert show_cron_job() is None
