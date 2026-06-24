"""config.load_config: missing file, missing section, and the happy path."""

import pytest

from zotrm.config import load_config


def test_load_config_missing_file_exits(tmp_path):
    with pytest.raises(SystemExit):
        load_config(tmp_path / "nope.ini")


def test_load_config_missing_section_exits(tmp_path):
    path = tmp_path / "config.ini"
    path.write_text("[zotero]\nlibrary_id = 1\n")  # no [remarkable]
    with pytest.raises(SystemExit):
        load_config(path)


def test_load_config_valid(tmp_path):
    path = tmp_path / "config.ini"
    path.write_text("[zotero]\nlibrary_id = 1\napi_key = k\n[remarkable]\ncollection = C\n")
    cfg = load_config(path)
    assert cfg["zotero"]["library_id"] == "1"
    assert cfg["remarkable"]["collection"] == "C"
