"""zotero helpers: connect(), collection lookup, and local PDF resolution."""

import configparser

import pytest
from conftest import FakeZotero, make_collection, make_pdf_child

from zotrm.zotero import connect, find_collection_key, local_pdf_path, pdf_child


def _cfg(**zotero):
    parser = configparser.ConfigParser()
    parser["zotero"] = {"library_id": "1", "api_key": "k", "library_type": "user", **zotero}
    return parser


def test_connect_builds_a_client():
    # pyzotero.Zotero does no network on construction.
    client = connect(_cfg())
    assert client is not None


def test_find_collection_key_found_and_missing():
    zot = FakeZotero()
    zot.collections_list = [make_collection("K1", "Papers"), make_collection("K2", "reMarkable")]
    assert find_collection_key(zot, "reMarkable") == "K2"
    with pytest.raises(SystemExit):
        find_collection_key(zot, "Nonexistent")


def test_pdf_child_skips_non_pdf_then_finds_pdf():
    zot = FakeZotero()
    note = {"key": "N", "data": {"contentType": "text/plain", "filename": "note.txt"}}
    zot.children_map = {"I": [note, make_pdf_child("attP", "paper.pdf")]}
    assert pdf_child(zot, "I") == ("attP", "paper.pdf")

    zot.children_map = {"I": [note]}  # no PDF at all
    assert pdf_child(zot, "I") is None


def test_local_pdf_path_present_absent_and_unset(tmp_path):
    # storage_dir set and file present -> returns the path
    store = tmp_path / "storage"
    (store / "ATT").mkdir(parents=True)
    (store / "ATT" / "p.pdf").write_bytes(b"%PDF")
    assert local_pdf_path(_cfg(storage_dir=str(store)), "ATT", "p.pdf") == store / "ATT" / "p.pdf"

    # storage_dir set but file missing -> None
    assert local_pdf_path(_cfg(storage_dir=str(store)), "ATT", "missing.pdf") is None

    # storage_dir unset -> None
    assert local_pdf_path(_cfg(), "ATT", "p.pdf") is None
