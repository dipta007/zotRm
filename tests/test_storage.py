"""storage: file_mode resolution and the zotero / webdav / none re-attach backends."""

import configparser
import zipfile
from io import BytesIO
from pathlib import Path

from conftest import FakeZotero, make_pdf_child

from zotrm.storage import download_pdf, file_mode, reattach


def _cfg(zotero=None, remarkable=None):
    p = configparser.ConfigParser()
    p["zotero"] = {"library_id": "1", "api_key": "k", **(zotero or {})}
    p["remarkable"] = {"collection": "C", **(remarkable or {})}
    return p


def _pdf(tmp_path):
    f = tmp_path / "good (annotated).pdf"
    f.write_bytes(b"%PDF annotated body")
    return f


# ---- file_mode resolution ---------------------------------------------------------


def test_file_mode_default_is_zotero():
    assert file_mode(_cfg()) == "zotero"


def test_file_mode_explicit():
    assert file_mode(_cfg({"file_mode": "webdav"})) == "webdav"
    assert file_mode(_cfg({"file_mode": "none"})) == "none"


def test_file_mode_backcompat_reattach_false():
    assert file_mode(_cfg(remarkable={"reattach": "false"})) == "none"


def test_file_mode_unknown_falls_back():
    assert file_mode(_cfg({"file_mode": "bogus"})) == "zotero"


# ---- none backend -----------------------------------------------------------------


def test_reattach_none_skips(tmp_path):
    zot = FakeZotero()
    assert reattach(zot, _cfg({"file_mode": "none"}), "P", _pdf(tmp_path)) is True
    assert zot.attachments == []
    assert zot.deleted == []


# ---- zotero backend ---------------------------------------------------------------


def test_reattach_zotero_uses_basename(tmp_path, monkeypatch):
    zot = FakeZotero()
    pdf = _pdf(tmp_path)
    monkeypatch.chdir(tmp_path)
    # pass a relative Path so resolve() is exercised
    assert reattach(zot, _cfg({"file_mode": "zotero"}), "P", Path(pdf.name)) is True
    # attached by basename only (not the full path)
    assert zot.attachments == [(["good (annotated).pdf"], "P")]


def test_reattach_zotero_replaces_existing(tmp_path):
    zot = FakeZotero()
    existing = make_pdf_child("OLD", "good (annotated).pdf")
    zot.children_map = {"P": [existing]}
    reattach(zot, _cfg({"file_mode": "zotero"}), "P", _pdf(tmp_path))
    assert zot.deleted == [existing]  # old copy removed after adding the new one


def test_reattach_skips_when_md5_unchanged(tmp_path):
    import hashlib

    zot = FakeZotero()
    pdf = _pdf(tmp_path)
    existing = make_pdf_child("OLD", "good (annotated).pdf")
    existing["data"]["md5"] = hashlib.md5(pdf.read_bytes()).hexdigest()
    zot.children_map = {"P": [existing]}

    assert reattach(zot, _cfg({"file_mode": "zotero"}), "P", pdf) is True
    assert zot.attachments == []
    assert zot.deleted == []


def test_reattach_failure_returns_false(tmp_path, monkeypatch):
    zot = FakeZotero()
    existing = make_pdf_child("OLD", "good (annotated).pdf")
    zot.children_map = {"P": [existing]}

    def boom(_paths, _parent):
        raise RuntimeError("quota exceeded")

    monkeypatch.setattr(zot, "attachment_simple", boom)
    assert reattach(zot, _cfg({"file_mode": "zotero"}), "P", _pdf(tmp_path)) is False
    assert zot.deleted == []  # previous annotated copy preserved on upload failure


def test_reattach_zotero_failure_dict_preserves_existing(tmp_path, monkeypatch):
    zot = FakeZotero()
    existing = make_pdf_child("OLD", "good (annotated).pdf")
    zot.children_map = {"P": [existing]}
    monkeypatch.setattr(
        zot, "attachment_simple", lambda _p, _k: {"failure": ["good (annotated).pdf"]}
    )
    assert reattach(zot, _cfg({"file_mode": "zotero"}), "P", _pdf(tmp_path)) is False
    assert zot.deleted == []


# ---- webdav backend ---------------------------------------------------------------


def test_reattach_webdav_uploads_zip_and_prop(tmp_path, monkeypatch):
    zot = FakeZotero()
    cfg = _cfg(
        {
            "file_mode": "webdav",
            "webdav_url": "https://dav.example.com/dav/me/",
            "webdav_user": "me",
            "webdav_pass": "secret",
        }
    )

    puts = []

    class _Resp:
        status = 201

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req):
        puts.append((req.full_url, req.data, req.get_header("Authorization")))
        return _Resp()

    monkeypatch.setattr("zotrm.storage.urllib.request.urlopen", fake_urlopen)

    assert reattach(zot, cfg, "P", _pdf(tmp_path)) is True

    urls = [u for u, _, _ in puts]
    assert "https://dav.example.com/dav/me/zotero/NEWKEY.zip" in urls
    assert "https://dav.example.com/dav/me/zotero/NEWKEY.prop" in urls
    # an attachment item was created with the parent + filename
    assert zot.created and zot.created[0]["parentItem"] == "P"
    # the .zip really contains the PDF under its basename
    zip_body = next(d for u, d, _ in puts if u.endswith(".zip"))
    with zipfile.ZipFile(BytesIO(zip_body)) as zf:
        assert zf.namelist() == ["good (annotated).pdf"]
    # the .prop carries an md5 hash, and auth header is set
    prop_body = next(d for u, d, _ in puts if u.endswith(".prop"))
    assert b"<hash>" in prop_body and b"<mtime>" in prop_body
    assert all(auth and auth.startswith("Basic ") for _, _, auth in puts)


def test_reattach_webdav_without_user_skips_auth(tmp_path, monkeypatch):
    zot = FakeZotero()
    cfg = _cfg({"file_mode": "webdav", "webdav_url": "https://dav/"})  # no user/pass

    headers = []

    class _Resp:
        status = 201

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req):
        headers.append(req.get_header("Authorization"))
        return _Resp()

    monkeypatch.setattr("zotrm.storage.urllib.request.urlopen", fake_urlopen)
    assert reattach(zot, cfg, "P", _pdf(tmp_path)) is True
    assert headers == [None, None]  # no auth header sent


def test_reattach_webdav_http_error_returns_false(tmp_path, monkeypatch):
    zot = FakeZotero()
    existing = make_pdf_child("OLD", "good (annotated).pdf")
    zot.children_map = {"P": [existing]}
    cfg = _cfg({"file_mode": "webdav", "webdav_url": "https://dav/", "webdav_user": "u"})

    class _Resp:
        status = 500

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr("zotrm.storage.urllib.request.urlopen", lambda req: _Resp())
    assert reattach(zot, cfg, "P", _pdf(tmp_path)) is False
    # newly created item rolled back; previous existing item untouched
    assert zot.deleted == [{"key": "NEWKEY", "version": 0}]


def test_reattach_webdav_create_item_failure_returns_false(tmp_path, monkeypatch):
    zot = FakeZotero()
    existing = make_pdf_child("OLD", "good (annotated).pdf")
    zot.children_map = {"P": [existing]}
    cfg = _cfg({"file_mode": "webdav", "webdav_url": "https://dav/"})
    monkeypatch.setattr(zot, "create_items", lambda _items: {"success": {}, "failed": {"0": "err"}})

    assert reattach(zot, cfg, "P", _pdf(tmp_path)) is False
    assert zot.deleted == []


def test_download_pdf_zotero_and_webdav(monkeypatch):
    zot = FakeZotero()
    zot.files["ATT"] = b"%PDF from zotero"
    assert download_pdf(zot, _cfg({"file_mode": "zotero"}), "ATT") == b"%PDF from zotero"

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("paper.pdf", b"%PDF from webdav")
    zip_bytes = buf.getvalue()

    seen_auth = []

    class _GetResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return zip_bytes

    def fake_urlopen(req):
        seen_auth.append(req.get_header("Authorization"))
        return _GetResp()

    monkeypatch.setattr("zotrm.storage.urllib.request.urlopen", fake_urlopen)
    cfg_auth = _cfg(
        {
            "file_mode": "webdav",
            "webdav_url": "https://dav/",
            "webdav_user": "u",
            "webdav_pass": "p",
        }
    )
    cfg_no_auth = _cfg({"file_mode": "webdav", "webdav_url": "https://dav/"})
    assert download_pdf(zot, cfg_auth, "ATT") == b"%PDF from webdav"
    assert download_pdf(zot, cfg_no_auth, "ATT") == b"%PDF from webdav"
    assert seen_auth[0].startswith("Basic ")
    assert seen_auth[1] is None
