"""pull: render annotated PDF (geta --a), re-attach, tag done, respect --dry-run."""

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


def _geta_fake(geta_calls=None):
    """Fake rmapi: `geta` writes '<x>-annotations.pdf' into its cwd (real behavior)."""

    def fake_run(cmd, **kwargs):
        if "geta" in cmd:
            if geta_calls is not None:
                geta_calls.append(list(cmd))
            (Path(kwargs["cwd"]) / "doc-annotations.pdf").write_bytes(b"%PDF annotated")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    return fake_run


def test_pull_renders_reattaches_and_tags(cfg, fake_zot, monkeypatch):
    parser, out = cfg
    _single_synced_item(fake_zot)
    monkeypatch.setattr("zotrm.cli.connect", lambda _cfg: fake_zot)

    geta_calls = []
    monkeypatch.setattr("zotrm.remarkable.subprocess.run", _geta_fake(geta_calls))

    cmd_pull(parser, dry_run=False)

    dest = out / "good (annotated).pdf"
    assert dest.exists()
    assert geta_calls[0] == ["rmapi", "geta", "--a", "/Papers/good"]  # --a + remote
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


def test_pull_reattach_error_still_tags_done(cfg, fake_zot, monkeypatch):
    parser, out = cfg
    _single_synced_item(fake_zot)
    monkeypatch.setattr("zotrm.cli.connect", lambda _cfg: fake_zot)

    def boom(_paths, _key):
        raise RuntimeError("no file storage")

    monkeypatch.setattr(fake_zot, "attachment_simple", boom)
    monkeypatch.setattr("zotrm.remarkable.subprocess.run", _geta_fake())

    cmd_pull(parser, dry_run=False)

    # re-attach failed but the item is still rendered, saved, and tagged done.
    assert (out / "good (annotated).pdf").exists()
    assert fake_zot.added_tags == [("G", "rm:annotated")]


def test_pull_skips_item_without_pdf(cfg, fake_zot, monkeypatch):
    parser, _out = cfg
    item = make_item("G", "Synced but no PDF", tags=["rm:synced"])
    fake_zot.collections_list = [make_collection("C1", "reMarkable")]
    fake_zot.items = {"C1": [item]}
    fake_zot.children_map = {"G": []}  # no attachments
    monkeypatch.setattr("zotrm.cli.connect", lambda _cfg: fake_zot)

    calls = []
    monkeypatch.setattr(
        "zotrm.remarkable.subprocess.run",
        lambda cmd, **k: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0, "", ""),
    )

    cmd_pull(parser, dry_run=False)
    assert calls == []
    assert fake_zot.added_tags == []


def test_pull_without_reattach_still_tags(tmp_path, fake_zot, monkeypatch):
    out = tmp_path / "annotated"
    parser = configparser.ConfigParser()
    parser.read_dict(
        {
            "zotero": {"library_id": "1", "api_key": "k"},
            "remarkable": {"collection": "reMarkable", "output_dir": str(out), "reattach": "false"},
        }
    )
    _single_synced_item(fake_zot)
    monkeypatch.setattr("zotrm.cli.connect", lambda _cfg: fake_zot)
    monkeypatch.setattr("zotrm.remarkable.subprocess.run", _geta_fake())

    cmd_pull(parser, dry_run=False)

    assert fake_zot.attachments == []  # reattach disabled -> never called
    assert fake_zot.added_tags == [("G", "rm:annotated")]


def test_pull_geta_failure_leaves_item_untouched(cfg, fake_zot, monkeypatch):
    parser, _out = cfg
    _single_synced_item(fake_zot)
    monkeypatch.setattr("zotrm.cli.connect", lambda _cfg: fake_zot)

    # geta exits non-zero (e.g. document not found)
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="not found")

    monkeypatch.setattr("zotrm.remarkable.subprocess.run", fake_run)

    cmd_pull(parser, dry_run=False)

    assert fake_zot.added_tags == []
    assert fake_zot.attachments == []


def test_pull_no_annotations_file_leaves_item_untouched(cfg, fake_zot, monkeypatch):
    parser, _out = cfg
    _single_synced_item(fake_zot)
    monkeypatch.setattr("zotrm.cli.connect", lambda _cfg: fake_zot)

    # geta exits 0 but produces no '*-annotations.pdf' (nothing to render)
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("zotrm.remarkable.subprocess.run", fake_run)

    cmd_pull(parser, dry_run=False)

    assert fake_zot.added_tags == []
    assert fake_zot.attachments == []
