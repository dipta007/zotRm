"""main() dispatch, first-run behavior, cmd_status, and the python -m shim."""

import importlib

import pytest
from conftest import FakeZotero, make_collection, make_item

from zotrm import cli


def _write_config(tmp_path):
    path = tmp_path / "config.ini"
    path.write_text("[zotero]\nlibrary_id = 1\napi_key = k\n[remarkable]\ncollection = C\n")
    return path


def test_main_dispatches_core_commands(tmp_path, monkeypatch):
    path = _write_config(tmp_path)
    calls = []
    monkeypatch.setattr(cli, "cmd_push", lambda cfg, dry: calls.append("push"))
    monkeypatch.setattr(cli, "cmd_pull", lambda cfg, dry: calls.append("pull"))
    monkeypatch.setattr(cli, "cmd_status", lambda cfg, dry: calls.append("status"))

    cli.main(["--config", str(path), "push"])
    cli.main(["--config", str(path), "pull"])
    cli.main(["--config", str(path), "status"])
    cli.main(["--config", str(path), "sync"])  # sync = pull then push
    assert calls == ["push", "pull", "status", "pull", "push"]


def test_main_config_subcommand(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr("zotrm.wizard.run_config_wizard", lambda p: seen.append(("wizard", p)))
    monkeypatch.setattr("zotrm.wizard.show_config", lambda p: seen.append(("show", p)))

    cli.main(["config"])
    cli.main(["config", "--show"])
    assert [s[0] for s in seen] == ["wizard", "show"]


def test_main_cron_subcommand(monkeypatch, capsys):
    monkeypatch.setattr("zotrm.cron.run_cron_setup", lambda p: print("setup"))
    monkeypatch.setattr("zotrm.cron.remove_cron_job", lambda: True)
    monkeypatch.setattr("zotrm.cron.show_cron_job", lambda: "0 * * * * x")

    cli.main(["cron"])
    cli.main(["cron", "--remove"])
    cli.main(["cron", "--show"])
    out = capsys.readouterr().out
    assert "setup" in out
    assert "Removed" in out
    assert "0 * * * * x" in out


def test_first_run_launches_wizard_then_continues(tmp_path, monkeypatch):
    path = tmp_path / "config.ini"
    monkeypatch.setattr(cli, "_interactive", lambda: True)

    def fake_wizard(p):
        p.write_text("[zotero]\nlibrary_id=1\napi_key=k\n[remarkable]\ncollection=C\n")
        return True

    monkeypatch.setattr("zotrm.wizard.run_config_wizard", fake_wizard)
    ran = []
    monkeypatch.setattr(cli, "cmd_status", lambda cfg, dry: ran.append(True))

    cli.main(["--config", str(path), "status"])
    assert ran == [True]


def test_first_run_aborted_wizard_stops(tmp_path, monkeypatch):
    path = tmp_path / "config.ini"
    monkeypatch.setattr(cli, "_interactive", lambda: True)
    monkeypatch.setattr("zotrm.wizard.run_config_wizard", lambda p: False)
    monkeypatch.setattr(cli, "cmd_status", lambda cfg, dry: pytest.fail("should not run"))

    cli.main(["--config", str(path), "status"])  # returns quietly, no command run


def test_non_interactive_missing_config_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "_interactive", lambda: False)
    with pytest.raises(SystemExit):
        cli.main(["--config", str(tmp_path / "nope.ini"), "status"])


def test_cmd_status_buckets(tmp_path, monkeypatch, capsys):
    fake = FakeZotero()
    fake.collections_list = [make_collection("C1", "C")]
    fake.items = {
        "C1": [
            make_item("Q", "Queued paper"),
            make_item("S", "On device", tags=["rm:synced"]),
            make_item("D", "Done paper", tags=["rm:synced", "rm:annotated"]),
        ]
    }
    monkeypatch.setattr(cli, "connect", lambda cfg: fake)
    path = _write_config(tmp_path)
    from zotrm.config import load_config

    cli.cmd_status(load_config(path), dry_run=False)
    out = capsys.readouterr().out
    assert "Queued (will push) (1)" in out
    assert "On reMarkable (reading) (1)" in out
    assert "Annotated (back in Zotero) (1)" in out


def test_interactive_returns_bool():
    assert isinstance(cli._interactive(), bool)


def test_dunder_main_importable():
    # Covers the `python -m zotrm` module import line.
    assert importlib.import_module("zotrm.__main__").main is cli.main
