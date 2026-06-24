"""push: skip synced / PDF-less items, tag on success, and respect --dry-run."""

import configparser

import pytest
from conftest import make_collection, make_item, make_pdf_child

from zotrm import remarkable
from zotrm.cli import cmd_push


@pytest.fixture
def cfg(tmp_path):
    storage = tmp_path / "storage"
    parser = configparser.ConfigParser()
    parser.read_dict(
        {
            "zotero": {
                "library_id": "1",
                "api_key": "k",
                "library_type": "user",
                "storage_dir": str(storage),
            },
            "remarkable": {
                "collection": "reMarkable",
                "folder": "/Papers",
                "mirror_subcollections": "true",
            },
        }
    )
    return parser, storage


def _store_pdf(storage, att_key, filename):
    folder = storage / att_key
    folder.mkdir(parents=True)
    (folder / filename).write_bytes(b"%PDF-1.4 local")


def test_push_tags_on_success_and_skips(cfg, fake_zot, rmapi_run, monkeypatch):
    parser, storage = cfg
    synced = make_item("S", "Already synced", tags=["rm:synced"])
    nopdf = make_item("N", "No pdf here")
    good = make_item("G", "Pushable paper")
    fake_zot.collections_list = [make_collection("C1", "reMarkable")]
    fake_zot.items = {"C1": [synced, nopdf, good]}
    fake_zot.children_map = {
        "S": [make_pdf_child("attS", "s.pdf")],
        "N": [],
        "G": [make_pdf_child("attG", "good.pdf")],
    }
    _store_pdf(storage, "attG", "good.pdf")
    monkeypatch.setattr("zotrm.cli.connect", lambda _cfg: fake_zot)

    cmd_push(parser, dry_run=False)

    # Only the eligible item is tagged; synced and PDF-less items are skipped.
    assert fake_zot.added_tags == [("G", "rm:synced")]

    put_calls = [call for call in rmapi_run.calls if call[1] == "put"]
    assert len(put_calls) == 1
    assert put_calls[0][2].endswith("good.pdf")  # source path
    assert put_calls[0][3] == "/Papers"  # destination folder


def test_push_dry_run_changes_nothing(cfg, fake_zot, rmapi_run, monkeypatch):
    parser, storage = cfg
    good = make_item("G", "Pushable paper")
    fake_zot.collections_list = [make_collection("C1", "reMarkable")]
    fake_zot.items = {"C1": [good]}
    fake_zot.children_map = {"G": [make_pdf_child("attG", "good.pdf")]}
    _store_pdf(storage, "attG", "good.pdf")
    monkeypatch.setattr("zotrm.cli.connect", lambda _cfg: fake_zot)

    cmd_push(parser, dry_run=True)

    assert fake_zot.added_tags == []
    assert rmapi_run.calls == []  # no mkdir, no put


def test_rmapi_missing_exits_cleanly(monkeypatch):
    def boom(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr("zotrm.remarkable.subprocess.run", boom)
    with pytest.raises(SystemExit):
        remarkable.rmapi("put", "x", "/Papers")
