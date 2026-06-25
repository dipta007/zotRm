"""Reconstruct reMarkable v6 annotations onto the original PDF as *editable* annotations.

The ddvk ``rmapi geta`` renderer can't read the reMarkable Paper Pro's v6 ``.rm``
format. Instead we download the raw bundle (``rmapi get``) and rebuild the marks
ourselves with ``rmscene`` + ``pypdf``:

- text highlights (``GlyphRange``) -> PDF ``/Highlight`` (Zotero imports these as
  native, editable highlights, carrying the highlighted text);
- pen strokes (``Line``) -> PDF ``/Ink`` with an appearance stream so every viewer
  paints them.

The reMarkable-canvas -> PDF-point transform is isolated in ``rm_to_pdf`` (calibrated
against a Paper Pro letter-size page); refine it there as more devices are verified.
"""

from __future__ import annotations

import io
import json
import logging
import zipfile
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Highlight
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    NumberObject,
    TextStringObject,
)
from rmscene import read_blocks

# These libraries log chatty warnings (pypdf annotation-copy notes, rmscene
# "newer format" notes) that aren't actionable for users; quiet them.
logging.getLogger("pypdf").setLevel(logging.ERROR)
logging.getLogger("rmscene").setLevel(logging.ERROR)

# --- coordinate transform (Paper Pro, calibrated against a 612x792 page) ---------
_CANVAS_W = 1620.0  # reMarkable Paper Pro canvas width, in rM units
_OFFSET_PT = 36.5  # empirical constant offset, in PDF points


def rm_to_pdf(x: float, y: float, page_w: float, page_h: float) -> tuple[float, float]:
    """Map a reMarkable v6 coordinate to a PDF point (origin bottom-left)."""
    s = page_w / _CANVAS_W
    return page_w / 2 + _OFFSET_PT + x * s, page_h + _OFFSET_PT - y * s


# --- parsing ---------------------------------------------------------------------
def parse_rm(rm_bytes: bytes) -> tuple[list[tuple[Any, str]], list[list[Any]]]:
    """Parse one v6 ``.rm`` into (highlights, strokes).

    highlights = [(rectangle, text), ...]   strokes = [[point, ...], ...]
    where rectangle has .x/.y/.w/.h and point has .x/.y (rM coordinates).
    """
    highlights: list[tuple[Any, str]] = []
    strokes: list[list[Any]] = []
    for block in read_blocks(io.BytesIO(rm_bytes)):
        val = getattr(getattr(block, "item", None), "value", None)
        if val is None:
            continue
        rects = getattr(val, "rectangles", None)
        text = getattr(val, "text", None)
        points = getattr(val, "points", None)
        if rects and text is not None:
            highlights.append((rects[0], text))
        elif points:
            strokes.append(list(points))
    return highlights, strokes


def pages_from_bundle(rmdoc: Path) -> dict[int, bytes]:
    """Map each annotated PDF page index to its raw ``.rm`` bytes."""
    with zipfile.ZipFile(rmdoc) as zf:
        names = zf.namelist()
        content_name = next((n for n in names if n.endswith(".content")), None)
        content = json.loads(zf.read(content_name)) if content_name else {}
        cpages = (content.get("cPages") or {}).get("pages")
        order = [p.get("id") for p in cpages] if cpages else (content.get("pages") or [])
        redirect = content.get("redirectionPageMap") or list(range(len(order)))
        result: dict[int, bytes] = {}
        for name in names:
            if not name.endswith(".rm"):
                continue
            uuid = Path(name).stem
            if uuid not in order:
                continue
            pos = order.index(uuid)
            pdf_idx = redirect[pos] if pos < len(redirect) else pos
            if pdf_idx is not None and pdf_idx >= 0:
                result[int(pdf_idx)] = zf.read(name)
    return result


# --- annotation building ---------------------------------------------------------
def add_highlight(
    writer: PdfWriter, page_idx: int, rect: Any, text: str, page_w: float, page_h: float
) -> None:
    x0, y_top = rm_to_pdf(rect.x, rect.y, page_w, page_h)
    x1, y_bot = rm_to_pdf(rect.x + rect.w, rect.y + rect.h, page_w, page_h)
    quad = ArrayObject(FloatObject(v) for v in (x0, y_top, x1, y_top, x0, y_bot, x1, y_bot))
    hl = Highlight(rect=(x0, y_bot, x1, y_top), quad_points=quad, highlight_color="ffd400")
    hl[NameObject("/Contents")] = TextStringObject(text)
    writer.add_annotation(page_number=page_idx, annotation=hl)


def add_ink(
    writer: PdfWriter, page_idx: int, strokes: list[list[Any]], page_w: float, page_h: float
) -> None:
    pdf_strokes = [[rm_to_pdf(p.x, p.y, page_w, page_h) for p in s] for s in strokes]
    xs = [x for s in pdf_strokes for x, _ in s]
    ys = [y for s in pdf_strokes for _, y in s]
    minx, miny, maxx, maxy = min(xs), min(ys), max(xs), max(ys)

    ink_list = ArrayObject()
    draw = "1 J 1 j 1.5 w 0 0 0 RG\n"  # round caps/joins, 1.5pt black stroke
    for s in pdf_strokes:
        arr = ArrayObject()
        for x, y in s:
            arr.extend([FloatObject(x), FloatObject(y)])
        ink_list.append(arr)
        draw += f"{s[0][0]:.2f} {s[0][1]:.2f} m\n"
        draw += "".join(f"{x:.2f} {y:.2f} l\n" for x, y in s[1:])
        draw += "S\n"

    appearance = DecodedStreamObject()
    appearance.set_data(draw.encode("latin-1"))
    appearance[NameObject("/Type")] = NameObject("/XObject")
    appearance[NameObject("/Subtype")] = NameObject("/Form")
    appearance[NameObject("/FormType")] = NumberObject(1)
    appearance[NameObject("/BBox")] = ArrayObject(FloatObject(v) for v in (minx, miny, maxx, maxy))
    ap_ref = writer._add_object(appearance)

    ink = DictionaryObject()
    ink[NameObject("/Type")] = NameObject("/Annot")
    ink[NameObject("/Subtype")] = NameObject("/Ink")
    ink[NameObject("/InkList")] = ink_list
    ink[NameObject("/Rect")] = ArrayObject(FloatObject(v) for v in (minx, miny, maxx, maxy))
    ink[NameObject("/C")] = ArrayObject([FloatObject(0), FloatObject(0), FloatObject(0)])
    ink[NameObject("/F")] = NumberObject(4)  # Print
    ap = DictionaryObject()
    ap[NameObject("/N")] = ap_ref
    ink[NameObject("/AP")] = ap
    writer.add_annotation(page_number=page_idx, annotation=ink)


def render_annotations(rmdoc: Path, original_pdf: Path, out: Path) -> bool:
    """Render the bundle's v6 annotations onto ``original_pdf`` -> ``out``.

    Returns True if any annotations were drawn (so the caller knows the file is
    worth keeping), False if the document has none.
    """
    page_rm = pages_from_bundle(rmdoc)
    if not page_rm:
        return False

    reader = PdfReader(str(original_pdf))
    writer = PdfWriter()
    writer.append(reader)

    drawn = False
    for idx, rm_bytes in page_rm.items():
        if idx >= len(reader.pages):
            continue
        page = reader.pages[idx]
        w, h = float(page.mediabox.width), float(page.mediabox.height)
        highlights, strokes = parse_rm(rm_bytes)
        for rect, text in highlights:
            add_highlight(writer, idx, rect, text, w, h)
            drawn = True
        if strokes:
            add_ink(writer, idx, strokes, w, h)
            drawn = True

    if drawn:
        with out.open("wb") as f:
            writer.write(f)
    return drawn
