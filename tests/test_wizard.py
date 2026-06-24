"""Config wizard: writes the INI, runs the checks, handles a failed Zotero test."""

import configparser

from conftest import FakeZotero

from zotrm.wizard import run_config_wizard


class _Answer:
    def __init__(self, value):
        self.value = value

    def ask(self):
        return self.value


class FakeQuestionary:
    """Returns canned answers in the order the wizard asks for them."""

    def __init__(self, answers):
        self._answers = list(answers)
        self._i = 0

    def _next(self):
        value = self._answers[self._i]
        self._i += 1
        return _Answer(value)

    def text(self, *a, **k):
        return self._next()

    def password(self, *a, **k):
        return self._next()

    def select(self, *a, **k):
        return self._next()

    def confirm(self, *a, **k):
        return self._next()

    def path(self, *a, **k):
        return self._next()


# Answer order: library_id, api_key, library_type, storage_dir,
# collection, folder, mirror?, output_dir, reattach?
_BASE_ANSWERS = ["123", "secret-key", "user", "", "MyColl", "/Papers", True]


def _good_zotero(_cfg):
    z = FakeZotero()
    z.item_count = 42
    return z


def test_wizard_writes_config(tmp_path, monkeypatch):
    answers = _BASE_ANSWERS + [str(tmp_path / "ann"), True]
    monkeypatch.setattr("zotrm.wizard.questionary", FakeQuestionary(answers))
    monkeypatch.setattr("zotrm.wizard.connect", _good_zotero)
    monkeypatch.setattr("zotrm.wizard.shutil.which", lambda _name: "/usr/bin/rmapi")

    path = tmp_path / "config.ini"
    assert run_config_wizard(path) is True

    cfg = configparser.ConfigParser()
    cfg.read(path)
    assert cfg["zotero"]["library_id"] == "123"
    assert cfg["zotero"]["api_key"] == "secret-key"
    assert cfg["zotero"]["library_type"] == "user"
    assert "storage_dir" not in cfg["zotero"]  # empty -> omitted
    assert cfg["remarkable"]["collection"] == "MyColl"
    assert cfg["remarkable"]["mirror_subcollections"] == "true"
    assert cfg["remarkable"]["reattach"] == "true"


def test_wizard_saves_anyway_when_zotero_fails(tmp_path, monkeypatch):
    # Extra trailing True answers the "save anyway?" confirm.
    answers = _BASE_ANSWERS + [str(tmp_path / "ann"), True, True]
    monkeypatch.setattr("zotrm.wizard.questionary", FakeQuestionary(answers))

    def boom(_cfg):
        raise RuntimeError("bad key")

    monkeypatch.setattr("zotrm.wizard.connect", boom)
    monkeypatch.setattr("zotrm.wizard.shutil.which", lambda _name: None)

    path = tmp_path / "config.ini"
    assert run_config_wizard(path) is True
    assert path.exists()


def test_wizard_aborts_when_declining_save(tmp_path, monkeypatch):
    answers = _BASE_ANSWERS + [str(tmp_path / "ann"), True, False]  # decline save
    monkeypatch.setattr("zotrm.wizard.questionary", FakeQuestionary(answers))

    def boom(_cfg):
        raise RuntimeError("bad key")

    monkeypatch.setattr("zotrm.wizard.connect", boom)
    monkeypatch.setattr("zotrm.wizard.shutil.which", lambda _name: None)

    path = tmp_path / "config.ini"
    assert run_config_wizard(path) is False
    assert not path.exists()
