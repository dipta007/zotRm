"""Config wizard: writing, prefill/keep-key, checks, failed-test, cancel, show."""

import configparser

import pytest
from conftest import FakeQuestionary, FakeZotero

from zotrm.wizard import _existing, run_config_wizard, show_config

# Answer order: library_id, api_key, library_type, storage_dir,
# collection, folder, mirror?, output_dir, reattach?
_BASE = ["123", "secret-key", "user", "", "MyColl", "/Papers", True]


def _good_zotero(_cfg):
    z = FakeZotero()
    z.item_count = 42
    return z


def _patch(monkeypatch, answers, *, connect=_good_zotero, rmapi="/usr/bin/rmapi"):
    monkeypatch.setattr("zotrm.wizard.questionary", FakeQuestionary(answers))
    monkeypatch.setattr("zotrm.wizard.connect", connect)
    monkeypatch.setattr("zotrm.wizard.shutil.which", lambda _name: rmapi)


def test_wizard_writes_config_with_storage_dir(tmp_path, monkeypatch):
    answers = [
        "123",
        "secret-key",
        "user",
        str(tmp_path / "store"),
        "MyColl",
        "/Papers",
        True,
        str(tmp_path / "ann"),
        False,
    ]
    _patch(monkeypatch, answers)

    path = tmp_path / "config.ini"
    assert run_config_wizard(path) is True

    cfg = configparser.ConfigParser()
    cfg.read(path)
    assert cfg["zotero"]["library_id"] == "123"
    assert cfg["zotero"]["storage_dir"] == str(tmp_path / "store")
    assert cfg["remarkable"]["mirror_subcollections"] == "true"
    assert cfg["remarkable"]["reattach"] == "false"


def test_wizard_prefills_and_keeps_api_key(tmp_path, monkeypatch):
    path = tmp_path / "config.ini"
    path.write_text(
        "[zotero]\nlibrary_id = 999\napi_key = old-key\nlibrary_type = group\n"
        "[remarkable]\ncollection = Old\nfolder = /Old\n"
        "mirror_subcollections = false\noutput_dir = /tmp/x\nreattach = false\n"
    )
    # api_key prompt becomes the "keep existing?" confirm (True) -> reuse old key.
    answers = ["999", True, "group", "", "Old", "/Old", False, "/tmp/x", False]
    _patch(monkeypatch, answers, rmapi=None)  # rmapi missing branch too

    assert run_config_wizard(path) is True
    cfg = configparser.ConfigParser()
    cfg.read(path)
    assert cfg["zotero"]["api_key"] == "old-key"
    assert cfg["zotero"]["library_type"] == "group"
    assert cfg["remarkable"]["mirror_subcollections"] == "false"


def test_wizard_saves_anyway_when_zotero_fails(tmp_path, monkeypatch):
    def boom(_cfg):
        raise RuntimeError("bad key")

    answers = _BASE + [str(tmp_path / "ann"), True, True]  # last True = save anyway
    _patch(monkeypatch, answers, connect=boom, rmapi=None)

    path = tmp_path / "config.ini"
    assert run_config_wizard(path) is True
    assert path.exists()


def test_wizard_aborts_when_declining_save(tmp_path, monkeypatch):
    def boom(_cfg):
        raise RuntimeError("bad key")

    answers = _BASE + [str(tmp_path / "ann"), True, False]  # decline save
    _patch(monkeypatch, answers, connect=boom)

    path = tmp_path / "config.ini"
    assert run_config_wizard(path) is False
    assert not path.exists()


def test_wizard_cancel_exits(tmp_path, monkeypatch):
    _patch(monkeypatch, [None])  # Ctrl-C on the first prompt
    with pytest.raises(SystemExit):
        run_config_wizard(tmp_path / "config.ini")


def test_existing_handles_partial_config(tmp_path):
    path = tmp_path / "config.ini"
    path.write_text("[zotero]\nlibrary_id = 5\n")  # no [remarkable] section
    assert _existing(path) == {"library_id": "5"}
    assert _existing(tmp_path / "absent.ini") == {}


def test_show_config(tmp_path, capsys):
    path = tmp_path / "config.ini"
    show_config(path)
    assert "No config" in capsys.readouterr().out

    path.write_text("[zotero]\nlibrary_id = 7\napi_key = topsecret\n[remarkable]\ncollection = C\n")
    show_config(path)
    out = capsys.readouterr().out
    assert "library_id = 7" in out
    assert "topsecret" not in out  # masked
    assert "********" in out
