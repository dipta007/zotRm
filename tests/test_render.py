"""render: coordinate transform, v6 parsing, page mapping, and PDF annotation build."""

import json
import zipfile
from types import SimpleNamespace

import pytest
from pypdf import PdfReader, PdfWriter

from zotrm.render import (
    add_highlight,
    add_ink,
    pages_from_bundle,
    parse_rm,
    render_annotations,
    rm_to_pdf,
)


def _block(value):
    return SimpleNamespace(item=SimpleNamespace(value=value))


def _tiny_pdf(path, pages=1):
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=612, height=792)
    with open(path, "wb") as f:
        w.write(f)


def _bundle(tmp_path, content, rm_files, name="b.rmdoc"):
    p = tmp_path / name
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("doc.content", json.dumps(content))
        for fname, data in rm_files.items():
            zf.writestr(fname, data)
    return p


# ---- transform -------------------------------------------------------------------


def test_rm_to_pdf_matches_calibration():
    # the values validated against the real "Continual learning," highlight
    px, py = rm_to_pdf(-572.4, 572.3, 612, 792)
    assert px == pytest.approx(126.2, abs=0.3)
    assert py == pytest.approx(612.3, abs=0.3)


# ---- parsing ---------------------------------------------------------------------


def test_parse_rm_splits_highlights_and_strokes(monkeypatch):
    rect = SimpleNamespace(x=1, y=2, w=3, h=4)
    blocks = [
        _block(SimpleNamespace(rectangles=[rect], text="hi")),  # highlight
        _block(SimpleNamespace(points=[SimpleNamespace(x=0, y=0)])),  # stroke
        _block(None),  # no value -> skipped
        _block(SimpleNamespace(other=1)),  # neither -> skipped
    ]
    monkeypatch.setattr("zotrm.render.read_blocks", lambda f: iter(blocks))

    highlights, strokes = parse_rm(b"x")
    assert highlights == [(rect, "hi")]
    assert len(strokes) == 1 and len(strokes[0]) == 1


# ---- page mapping ----------------------------------------------------------------


def test_pages_from_bundle_cpages(tmp_path):
    content = {"cPages": {"pages": [{"id": "P1"}, {"id": "P2"}]}, "redirectionPageMap": [0, 1]}
    b = _bundle(tmp_path, content, {"doc/P1.rm": b"aaa"})
    assert pages_from_bundle(b) == {0: b"aaa"}


def test_pages_from_bundle_pages_fallback_and_redirect(tmp_path):
    # flat "pages" list; P1 redirects to PDF page 5, P2 to -1 (inserted -> skipped)
    content = {"pages": ["P1", "P2"], "redirectionPageMap": [5, -1]}
    b = _bundle(tmp_path, content, {"doc/P1.rm": b"aaa", "doc/P2.rm": b"bbb"})
    assert pages_from_bundle(b) == {5: b"aaa"}


def test_pages_from_bundle_null_redirect_and_short_map(tmp_path):
    # null redirect entry -> skipped; map shorter than order -> falls back to position
    content = {"pages": ["P1", "P2"], "redirectionPageMap": [None]}
    b = _bundle(tmp_path, content, {"doc/P1.rm": b"a", "doc/P2.rm": b"b"})
    assert pages_from_bundle(b) == {1: b"b"}  # P1 null -> skip; P2 pos 1 (map too short)


def test_pages_from_bundle_unknown_and_no_content(tmp_path):
    # .rm whose uuid isn't listed is skipped
    b = _bundle(tmp_path, {"pages": ["P1"]}, {"doc/UNKNOWN.rm": b"x"})
    assert pages_from_bundle(b) == {}
    # bundle with no .content at all
    p = tmp_path / "nocontent.rmdoc"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("doc/P1.rm", b"x")
    assert pages_from_bundle(p) == {}


# ---- annotation building ---------------------------------------------------------


def test_add_highlight_creates_highlight_with_text():
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    rect = SimpleNamespace(x=-572.4, y=572.3, w=256.2, h=32.2)
    add_highlight(writer, 0, rect, "Continual learning,", 612, 792)

    annots = writer.pages[0]["/Annots"]
    assert len(annots) == 1
    o = annots[0].get_object()
    assert o["/Subtype"] == "/Highlight"
    assert str(o["/Contents"]) == "Continual learning,"


def test_add_ink_creates_ink_with_appearance():
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    strokes = [[SimpleNamespace(x=-700, y=600), SimpleNamespace(x=-680, y=620)]]
    add_ink(writer, 0, strokes, 612, 792)

    o = writer.pages[0]["/Annots"][0].get_object()
    assert o["/Subtype"] == "/Ink"
    assert len(o["/InkList"]) == 1
    assert "/AP" in o


# ---- end to end ------------------------------------------------------------------


def test_render_annotations_draws_both(tmp_path, monkeypatch):
    orig = tmp_path / "orig.pdf"
    _tiny_pdf(orig, pages=1)
    content = {"cPages": {"pages": [{"id": "P1"}]}, "redirectionPageMap": [0]}
    bundle = _bundle(tmp_path, content, {"doc/P1.rm": b"x"})
    out = tmp_path / "out.pdf"

    rect = SimpleNamespace(x=-100, y=100, w=50, h=20)
    blocks = [
        _block(SimpleNamespace(rectangles=[rect], text="hi")),
        _block(
            SimpleNamespace(points=[SimpleNamespace(x=-100, y=100), SimpleNamespace(x=-80, y=120)])
        ),
    ]
    monkeypatch.setattr("zotrm.render.read_blocks", lambda f: iter(blocks))

    assert render_annotations(bundle, orig, out) is True
    subs = {a.get_object()["/Subtype"] for a in PdfReader(str(out)).pages[0]["/Annots"]}
    assert "/Highlight" in subs
    assert "/Ink" in subs


def test_render_annotations_multi_page(tmp_path, monkeypatch):
    orig = tmp_path / "orig.pdf"
    _tiny_pdf(orig, pages=2)
    content = {"cPages": {"pages": [{"id": "P1"}, {"id": "P2"}]}, "redirectionPageMap": [0, 1]}
    bundle = _bundle(tmp_path, content, {"doc/P1.rm": b"a", "doc/P2.rm": b"b"})
    out = tmp_path / "out.pdf"

    rect = SimpleNamespace(x=-100, y=100, w=50, h=20)
    stroke = [SimpleNamespace(x=-100, y=100), SimpleNamespace(x=-80, y=120)]
    # page 0: highlight only; page 1: stroke only
    results = iter([([(rect, "hi")], []), ([], [stroke])])
    monkeypatch.setattr("zotrm.render.parse_rm", lambda _b: next(results))

    assert render_annotations(bundle, orig, out) is True
    r = PdfReader(str(out))
    subs0 = {a.get_object()["/Subtype"] for a in (r.pages[0].get("/Annots") or [])}
    subs1 = {a.get_object()["/Subtype"] for a in (r.pages[1].get("/Annots") or [])}
    assert subs0 == {"/Highlight"}  # highlight, no ink
    assert subs1 == {"/Ink"}  # ink, no highlight


def test_render_annotations_no_annotated_pages(tmp_path):
    bundle = _bundle(tmp_path, {"pages": []}, {})
    assert render_annotations(bundle, tmp_path / "missing.pdf", tmp_path / "o.pdf") is False


def test_render_annotations_page_out_of_range(tmp_path, monkeypatch):
    orig = tmp_path / "orig.pdf"
    _tiny_pdf(orig, pages=1)  # only 1 page
    content = {"cPages": {"pages": [{"id": "P1"}]}, "redirectionPageMap": [5]}  # -> page 5
    bundle = _bundle(tmp_path, content, {"doc/P1.rm": b"x"})
    out = tmp_path / "out.pdf"
    monkeypatch.setattr("zotrm.render.read_blocks", lambda f: iter([]))

    assert render_annotations(bundle, orig, out) is False  # page 5 skipped, nothing drawn
    assert not out.exists()
