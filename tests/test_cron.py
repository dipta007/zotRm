"""Cron helpers: schedule mapping, line building, and idempotent crontab merge."""

import subprocess
from pathlib import Path

import pytest
from conftest import FakeQuestionary

from zotrm.config import DEFAULT_CONFIG
from zotrm.cron import (
    MARKER,
    build_cron_line,
    build_schedule,
    install_cron_line,
    remove_cron_job,
    run_cron_setup,
    show_cron_job,
    zotrm_command,
)


def test_build_schedule_presets_and_followups():
    assert build_schedule("Every hour") == "0 * * * *"
    assert build_schedule("Every 6 hours") == "0 */6 * * *"
    assert build_schedule("Once a day", time="07:30") == "30 7 * * *"
    assert build_schedule("Once a week", time="09:05", weekday=1) == "5 9 * * 1"
    assert build_schedule("Advanced (cron expression)", custom="*/15 * * * *") == "*/15 * * * *"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"preset": "Once a day", "time": "99:99"},
        {"preset": "Once a day", "time": None},
        {"preset": "Advanced (cron expression)", "custom": "nope"},
        {"preset": "Mystery preset", "time": None},  # fails the time check
        {"preset": "Mystery preset", "time": "07:00"},  # reaches "unknown schedule"
    ],
)
def test_build_schedule_rejects_bad_input(kwargs):
    with pytest.raises(SystemExit):
        build_schedule(**kwargs)


def test_zotrm_command_uses_exe_and_config(monkeypatch):
    monkeypatch.setattr("zotrm.cron.shutil.which", lambda _n: "/bin/zotrm")
    assert zotrm_command(DEFAULT_CONFIG) == "/bin/zotrm sync"
    custom = Path("/tmp/other.ini")
    assert zotrm_command(custom) == f"/bin/zotrm --config {custom} sync"


def test_zotrm_command_falls_back_to_module(monkeypatch):
    monkeypatch.setattr("zotrm.cron.shutil.which", lambda _n: None)
    monkeypatch.setattr("zotrm.cron.sys.executable", "/py")
    assert zotrm_command(DEFAULT_CONFIG) == "/py -m zotrm sync"


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


def test_crontab_missing_binary_exits(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError

    monkeypatch.setattr("zotrm.cron.subprocess.run", boom)
    with pytest.raises(SystemExit):
        install_cron_line("x")


def test_write_crontab_failure_exits(monkeypatch):
    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["crontab", "-l"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="denied")

    monkeypatch.setattr("zotrm.cron.subprocess.run", fake_run)
    with pytest.raises(SystemExit):
        install_cron_line("x")


def test_run_cron_setup_no_config(tmp_path, capsys):
    run_cron_setup(tmp_path / "missing.ini")
    assert "Run 'zotrm config' first" in capsys.readouterr().out


def _config(tmp_path):
    path = tmp_path / "config.ini"
    path.write_text("[zotero]\nlibrary_id = 1\napi_key = k\n[remarkable]\ncollection = C\n")
    return path


def test_run_cron_setup_installs_daily(tmp_path, monkeypatch):
    path = _config(tmp_path)
    monkeypatch.setattr("zotrm.cron.shutil.which", lambda _n: "/bin/zotrm")
    # select preset -> "Once a day", time -> "07:30", confirm install -> True
    monkeypatch.setattr("zotrm.cron.questionary", FakeQuestionary(["Once a day", "07:30", True]))
    state = {"lines": []}
    monkeypatch.setattr("zotrm.cron.subprocess.run", _fake_crontab(state))

    run_cron_setup(path)

    markers = [line for line in state["lines"] if MARKER in line]
    assert len(markers) == 1
    assert markers[0].startswith("30 7 * * * /bin/zotrm")
    assert str(path.parent / "sync.log") in markers[0]


def test_run_cron_setup_weekly_then_decline(tmp_path, monkeypatch):
    path = _config(tmp_path)
    monkeypatch.setattr("zotrm.cron.shutil.which", lambda _n: "/bin/zotrm")
    # weekly -> Tuesday -> 09:00 -> decline install (False)
    monkeypatch.setattr(
        "zotrm.cron.questionary", FakeQuestionary(["Once a week", "Tuesday", "09:00", False])
    )
    called = []
    monkeypatch.setattr("zotrm.cron.subprocess.run", lambda *a, **k: called.append(a))

    run_cron_setup(path)
    assert called == []  # declined -> crontab untouched


def test_run_cron_setup_hourly_no_followup(tmp_path, monkeypatch):
    path = _config(tmp_path)
    monkeypatch.setattr("zotrm.cron.shutil.which", lambda _n: "/bin/zotrm")
    monkeypatch.setattr("zotrm.cron.questionary", FakeQuestionary(["Every hour", True]))
    state = {"lines": []}
    monkeypatch.setattr("zotrm.cron.subprocess.run", _fake_crontab(state))

    run_cron_setup(path)
    assert any(line.startswith("0 * * * *") for line in state["lines"])


def test_run_cron_setup_cancelled(tmp_path, monkeypatch):
    path = _config(tmp_path)
    monkeypatch.setattr("zotrm.cron.questionary", FakeQuestionary([None]))  # Ctrl-C
    with pytest.raises(SystemExit):
        run_cron_setup(path)


def test_run_cron_setup_advanced(tmp_path, monkeypatch):
    path = _config(tmp_path)
    monkeypatch.setattr("zotrm.cron.shutil.which", lambda _n: "/bin/zotrm")
    monkeypatch.setattr(
        "zotrm.cron.questionary",
        FakeQuestionary(["Advanced (cron expression)", "*/30 * * * *", True]),
    )
    state = {"lines": []}
    monkeypatch.setattr("zotrm.cron.subprocess.run", _fake_crontab(state))

    run_cron_setup(path)
    assert any(line.startswith("*/30 * * * *") for line in state["lines"])
