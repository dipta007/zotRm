"""Config wizard: writing, prefill/keep-key, file_mode, webdav, checks, cancel, show."""

import configparser

import pytest
from conftest import FakeQuestionary, FakeZotero

from zotrm.wizard import _existing, run_config_wizard, show_config

# Answer order: library_id, api_key, library_type, storage_dir,
# collection, folder, mirror?, output_dir, file_mode, [webdav_url, user, pass]
_BASE = ["123", "secret-key", "user", "", "MyColl", "/Papers", True]


def _good_zotero(_cfg):
    z = FakeZotero()
    z.item_count = 42
    return z


def _patch(monkeypatch, answers, *, connect=_good_zotero, rmapi="/usr/bin/rmapi"):
    monkeypatch.setattr("zotrm.wizard.questionary", FakeQuestionary(answers))
    monkeypatch.setattr("zotrm.wizard.connect", connect)
    monkeypatch.setattr("zotrm.wizard.shutil.which", lambda _name: rmapi)


def test_wizard_writes_config(tmp_path, monkeypatch):
    answers = [
        "123",
        "secret-key",
        "user",
        str(tmp_path / "store"),
        "MyColl",
        "/Papers",
        True,
        str(tmp_path / "ann"),
        "zotero",
    ]
    _patch(monkeypatch, answers)

    path = tmp_path / "config.ini"
    assert run_config_wizard(path) is True

    cfg = configparser.ConfigParser()
    cfg.read(path)
    assert cfg["zotero"]["library_id"] == "123"
    assert cfg["zotero"]["storage_dir"] == str(tmp_path / "store")
    assert cfg["zotero"]["file_mode"] == "zotero"
    assert cfg["remarkable"]["mirror_subcollections"] == "true"
    assert "reattach" not in cfg["remarkable"]


def test_wizard_webdav_collects_credentials(tmp_path, monkeypatch):
    answers = _BASE + [str(tmp_path / "ann"), "webdav", "https://dav.example.com/me", "me", "pw"]
    _patch(monkeypatch, answers)

    path = tmp_path / "config.ini"
    assert run_config_wizard(path) is True

    cfg = configparser.ConfigParser()
    cfg.read(path)
    assert cfg["zotero"]["file_mode"] == "webdav"
    assert cfg["zotero"]["webdav_url"] == "https://dav.example.com/me"
    assert cfg["zotero"]["webdav_user"] == "me"
    assert cfg["zotero"]["webdav_pass"] == "pw"


def test_wizard_prefills_and_keeps_api_key(tmp_path, monkeypatch):
    path = tmp_path / "config.ini"
    path.write_text(
        "[zotero]\nlibrary_id = 999\napi_key = old-key\nlibrary_type = group\nfile_mode = none\n"
        "[remarkable]\ncollection = Old\nfolder = /Old\n"
        "mirror_subcollections = false\noutput_dir = /tmp/x\n"
    )
    # api_key prompt becomes the "keep existing?" confirm (True) -> reuse old key.
    answers = ["999", True, "group", "", "Old", "/Old", False, "/tmp/x", "none"]
    _patch(monkeypatch, answers, rmapi=None)  # rmapi missing branch too

    assert run_config_wizard(path) is True
    cfg = configparser.ConfigParser()
    cfg.read(path)
    assert cfg["zotero"]["api_key"] == "old-key"
    assert cfg["zotero"]["library_type"] == "group"
    assert cfg["zotero"]["file_mode"] == "none"
    assert cfg["remarkable"]["mirror_subcollections"] == "false"


def test_wizard_saves_anyway_when_zotero_fails(tmp_path, monkeypatch):
    def boom(_cfg):
        raise RuntimeError("bad key")

    answers = _BASE + [str(tmp_path / "ann"), "zotero", True]  # last True = save anyway
    _patch(monkeypatch, answers, connect=boom, rmapi=None)

    path = tmp_path / "config.ini"
    assert run_config_wizard(path) is True
    assert path.exists()


def test_wizard_aborts_when_declining_save(tmp_path, monkeypatch):
    def boom(_cfg):
        raise RuntimeError("bad key")

    answers = _BASE + [str(tmp_path / "ann"), "zotero", False]  # decline save
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

    path.write_text(
        "[zotero]\nlibrary_id = 7\napi_key = topsecret\nfile_mode = webdav\n"
        "webdav_pass = davsecret\n[remarkable]\ncollection = C\n"
    )
    show_config(path)
    out = capsys.readouterr().out
    assert "library_id = 7" in out
    assert "topsecret" not in out  # api key masked
    assert "davsecret" not in out  # webdav password masked
    assert "********" in out
