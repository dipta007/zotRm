"""sync: first run pushes the original; later runs refresh one annotated copy."""

import configparser
import subprocess
from pathlib import Path

import pytest
from conftest import make_collection, make_item, make_pdf_child

from zotrm import remarkable
from zotrm.cli import cmd_sync


def test_rmapi_missing_exits_cleanly(monkeypatch):
    def boom(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr("zotrm.remarkable.subprocess.run", boom)
    with pytest.raises(SystemExit):
        remarkable.rmapi("put", "x", "/Papers")


@pytest.fixture
def cfg(tmp_path):
    storage = tmp_path / "storage"
    out = tmp_path / "annotated"
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
                "output_dir": str(out),
            },
        }
    )
    return parser, storage, out


def _store_pdf(storage, att_key, filename):
    folder = storage / att_key
    folder.mkdir(parents=True)
    (folder / filename).write_bytes(b"%PDF-1.4 local")


def _geta_fake(geta_calls=None):
    def fake_run(cmd, **kwargs):
        if "geta" in cmd:
            if geta_calls is not None:
                geta_calls.append(list(cmd))
            (Path(kwargs["cwd"]) / "doc-annotations.pdf").write_bytes(b"%PDF annotated")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    return fake_run


# ---- first run: push the original -------------------------------------------------


def test_sync_first_run_pushes_original(cfg, fake_zot, rmapi_run, monkeypatch):
    parser, storage, _out = cfg
    item = make_item("G", "Pushable paper")  # no rm:synced yet
    fake_zot.collections_list = [make_collection("C1", "reMarkable")]
    fake_zot.items = {"C1": [item]}
    fake_zot.children_map = {"G": [make_pdf_child("attG", "good.pdf")]}
    _store_pdf(storage, "attG", "good.pdf")
    monkeypatch.setattr("zotrm.cli.connect", lambda _cfg: fake_zot)

    cmd_sync(parser, dry_run=False)

    assert fake_zot.added_tags == [("G", "rm:synced")]
    put = [c for c in rmapi_run.calls if c[1] == "put"]
    assert put[0][2].endswith("good.pdf")


def test_sync_push_skips_annotated_picks_original(cfg, fake_zot, rmapi_run, monkeypatch):
    parser, storage, _out = cfg
    item = make_item("G", "Paper")
    fake_zot.collections_list = [make_collection("C1", "reMarkable")]
    fake_zot.items = {"C1": [item]}
    # annotated copy listed first; sync must push the ORIGINAL
    fake_zot.children_map = {
        "G": [
            make_pdf_child("attA", "good (annotated).pdf"),
            make_pdf_child("attG", "good.pdf"),
        ]
    }
    _store_pdf(storage, "attG", "good.pdf")
    monkeypatch.setattr("zotrm.cli.connect", lambda _cfg: fake_zot)

    cmd_sync(parser, dry_run=False)

    put = [c for c in rmapi_run.calls if c[1] == "put"]
    assert put[0][2].endswith("good.pdf")  # original, not the annotated copy


def test_sync_push_via_api_when_not_local(cfg, fake_zot, rmapi_run, monkeypatch):
    parser, _storage, _out = cfg  # storage exists but has no file -> API download
    item = make_item("G", "Paper")
    fake_zot.collections_list = [make_collection("C1", "reMarkable")]
    fake_zot.items = {"C1": [item]}
    fake_zot.children_map = {"G": [make_pdf_child("attG", "good.pdf")]}
    fake_zot.files = {"attG": b"%PDF downloaded"}
    monkeypatch.setattr("zotrm.cli.connect", lambda _cfg: fake_zot)

    cmd_sync(parser, dry_run=False)
    assert fake_zot.added_tags == [("G", "rm:synced")]


def test_sync_push_failure_not_tagged(cfg, fake_zot, monkeypatch):
    parser, storage, _out = cfg
    item = make_item("G", "Paper")
    fake_zot.collections_list = [make_collection("C1", "reMarkable")]
    fake_zot.items = {"C1": [item]}
    fake_zot.children_map = {"G": [make_pdf_child("attG", "good.pdf")]}
    _store_pdf(storage, "attG", "good.pdf")
    monkeypatch.setattr("zotrm.cli.connect", lambda _cfg: fake_zot)

    def fail(cmd, **kwargs):
        code = 0 if cmd[1] == "mkdir" else 1
        return subprocess.CompletedProcess(cmd, code, stdout="", stderr="boom")

    monkeypatch.setattr("zotrm.remarkable.subprocess.run", fail)

    cmd_sync(parser, dry_run=False)
    assert fake_zot.added_tags == []


def test_sync_skips_item_without_original_pdf(cfg, fake_zot, rmapi_run, monkeypatch):
    parser, _storage, _out = cfg
    item = make_item("G", "Only annotated")
    fake_zot.collections_list = [make_collection("C1", "reMarkable")]
    fake_zot.items = {"C1": [item]}
    fake_zot.children_map = {"G": [make_pdf_child("attA", "good (annotated).pdf")]}
    monkeypatch.setattr("zotrm.cli.connect", lambda _cfg: fake_zot)

    cmd_sync(parser, dry_run=False)
    assert rmapi_run.calls == []
    assert fake_zot.added_tags == []


def test_sync_dry_run_changes_nothing(cfg, fake_zot, rmapi_run, monkeypatch):
    parser, storage, _out = cfg
    item = make_item("G", "Paper")
    fake_zot.collections_list = [make_collection("C1", "reMarkable")]
    fake_zot.items = {"C1": [item]}
    fake_zot.children_map = {"G": [make_pdf_child("attG", "good.pdf")]}
    _store_pdf(storage, "attG", "good.pdf")
    monkeypatch.setattr("zotrm.cli.connect", lambda _cfg: fake_zot)

    cmd_sync(parser, dry_run=True)
    assert fake_zot.added_tags == []
    assert rmapi_run.calls == []


# ---- later runs: refresh the annotated copy ---------------------------------------


def _synced_item(fake_zot):
    item = make_item("G", "Annotated paper", tags=["rm:synced"])
    fake_zot.collections_list = [make_collection("C1", "reMarkable")]
    fake_zot.items = {"C1": [item]}
    fake_zot.children_map = {"G": [make_pdf_child("attG", "good.pdf")]}


def test_sync_refresh_calls_reattach_and_tags(cfg, fake_zot, monkeypatch):
    parser, _storage, out = cfg
    _synced_item(fake_zot)
    monkeypatch.setattr("zotrm.cli.connect", lambda _cfg: fake_zot)

    calls = []
    monkeypatch.setattr(
        "zotrm.cli.reattach", lambda zot, c, key, dest: calls.append((key, dest)) or True
    )
    geta_calls = []
    monkeypatch.setattr("zotrm.remarkable.subprocess.run", _geta_fake(geta_calls))

    cmd_sync(parser, dry_run=False)

    dest = out / "good (annotated).pdf"
    assert dest.exists()
    assert geta_calls[0] == ["rmapi", "geta", "--a", "/Papers/good"]
    assert calls == [("G", dest)]
    assert fake_zot.added_tags == [("G", "rm:annotated")]


def test_sync_refresh_reattach_failure_saves_local_not_tagged(cfg, fake_zot, monkeypatch):
    parser, _storage, out = cfg
    _synced_item(fake_zot)
    monkeypatch.setattr("zotrm.cli.connect", lambda _cfg: fake_zot)
    monkeypatch.setattr("zotrm.cli.reattach", lambda *a: False)
    monkeypatch.setattr("zotrm.remarkable.subprocess.run", _geta_fake())

    cmd_sync(parser, dry_run=False)

    assert (out / "good (annotated).pdf").exists()  # local copy kept
    assert fake_zot.added_tags == []  # not marked done -> retries next sync


def test_sync_refresh_no_annotations(cfg, fake_zot, monkeypatch):
    parser, _storage, _out = cfg
    _synced_item(fake_zot)
    monkeypatch.setattr("zotrm.cli.connect", lambda _cfg: fake_zot)
    monkeypatch.setattr("zotrm.cli.reattach", lambda *a: pytest.fail("should not attach"))

    def geta_fails(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="no annotations")

    monkeypatch.setattr("zotrm.remarkable.subprocess.run", geta_fails)

    cmd_sync(parser, dry_run=False)
    assert fake_zot.added_tags == []


def test_sync_refresh_dry_run(cfg, fake_zot, monkeypatch):
    parser, _storage, _out = cfg
    _synced_item(fake_zot)
    monkeypatch.setattr("zotrm.cli.connect", lambda _cfg: fake_zot)
    calls = []
    monkeypatch.setattr("zotrm.remarkable.subprocess.run", lambda cmd, **k: calls.append(cmd))

    cmd_sync(parser, dry_run=True)
    assert calls == []
    assert fake_zot.added_tags == []


def test_sync_refresh_already_done_not_retagged(cfg, fake_zot, monkeypatch):
    parser, _storage, out = cfg
    item = make_item("G", "Done paper", tags=["rm:synced", "rm:annotated"])
    fake_zot.collections_list = [make_collection("C1", "reMarkable")]
    fake_zot.items = {"C1": [item]}
    fake_zot.children_map = {"G": [make_pdf_child("attG", "good.pdf")]}
    monkeypatch.setattr("zotrm.cli.connect", lambda _cfg: fake_zot)
    monkeypatch.setattr("zotrm.cli.reattach", lambda *a: True)
    monkeypatch.setattr("zotrm.remarkable.subprocess.run", _geta_fake())

    cmd_sync(parser, dry_run=False)

    assert (out / "good (annotated).pdf").exists()  # still refreshed
    assert fake_zot.added_tags == []  # tag already present, not added again
