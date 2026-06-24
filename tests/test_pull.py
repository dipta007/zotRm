"""pull: render annotated PDF (geta), re-attach, tag done, respect --dry-run."""

import configparser
import subprocess
from pathlib import Path

import pytest
from conftest import make_collection, make_item, make_pdf_child

from zotrm.cli import cmd_pull


@pytest.fixture
def cfg(tmp_path):
    out = tmp_path / "annotated"
    parser = configparser.ConfigParser()
    parser.read_dict(
        {
            "zotero": {"library_id": "1", "api_key": "k", "library_type": "user"},
            "remarkable": {
                "collection": "reMarkable",
                "folder": "/Papers",
                "mirror_subcollections": "true",
                "output_dir": str(out),
                "reattach": "true",
            },
        }
    )
    return parser, out


def _single_synced_item(fake_zot):
    item = make_item("G", "Annotated paper", tags=["rm:synced"])
    fake_zot.collections_list = [make_collection("C1", "reMarkable")]
    fake_zot.items = {"C1": [item]}
    fake_zot.children_map = {"G": [make_pdf_child("attG", "good.pdf")]}


def test_pull_renders_reattaches_and_tags(cfg, fake_zot, monkeypatch):
    parser, out = cfg
    _single_synced_item(fake_zot)
    monkeypatch.setattr("zotrm.cli.connect", lambda _cfg: fake_zot)

    geta_calls = []

    def fake_run(cmd, **kwargs):
        if cmd[1] == "geta":
            geta_calls.append(list(cmd))
            Path(cmd[3]).write_bytes(b"%PDF annotated")  # geta renders the file
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("zotrm.remarkable.subprocess.run", fake_run)

    cmd_pull(parser, dry_run=False)

    dest = out / "good (annotated).pdf"
    assert dest.exists()
    assert geta_calls[0][2] == "/Papers/good"  # remote = folder/stem
    assert fake_zot.attachments == [([str(dest)], "G")]
    assert fake_zot.added_tags == [("G", "rm:annotated")]


def test_pull_dry_run_changes_nothing(cfg, fake_zot, monkeypatch):
    parser, out = cfg
    _single_synced_item(fake_zot)
    monkeypatch.setattr("zotrm.cli.connect", lambda _cfg: fake_zot)

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("zotrm.remarkable.subprocess.run", fake_run)

    cmd_pull(parser, dry_run=True)

    assert calls == []
    assert fake_zot.attachments == []
    assert fake_zot.added_tags == []
    assert not (out / "good (annotated).pdf").exists()


def test_pull_skips_unsynced_and_done(cfg, fake_zot, monkeypatch):
    parser, _out = cfg
    unsynced = make_item("U", "Not pushed yet")
    done = make_item("D", "Already done", tags=["rm:synced", "rm:annotated"])
    fake_zot.collections_list = [make_collection("C1", "reMarkable")]
    fake_zot.items = {"C1": [unsynced, done]}
    fake_zot.children_map = {
        "U": [make_pdf_child("attU", "u.pdf")],
        "D": [make_pdf_child("attD", "d.pdf")],
    }
    monkeypatch.setattr("zotrm.cli.connect", lambda _cfg: fake_zot)

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("zotrm.remarkable.subprocess.run", fake_run)

    cmd_pull(parser, dry_run=False)

    assert calls == []  # neither item triggers geta
    assert fake_zot.added_tags == []
    assert fake_zot.attachments == []


def test_pull_no_annotations_yet_leaves_item_untouched(cfg, fake_zot, monkeypatch):
    parser, _out = cfg
    _single_synced_item(fake_zot)
    monkeypatch.setattr("zotrm.cli.connect", lambda _cfg: fake_zot)

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="not found")

    monkeypatch.setattr("zotrm.remarkable.subprocess.run", fake_run)

    cmd_pull(parser, dry_run=False)

    assert fake_zot.added_tags == []
    assert fake_zot.attachments == []
