"""Spike v3: v6 highlight -> /Highlight; pen strokes -> /Ink WITH appearance stream."""

import sys
import zipfile
from pathlib import Path

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
from rmscene.scene_items import GlyphRange, Line

ORIG, RMDOC, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
S, OX, OY = 0.379, 342.8, 829.5


def to_pdf(x, y):
    return OX + x * S, OY - y * S


reader = PdfReader(ORIG)
with zipfile.ZipFile(RMDOC) as zf:
    rm_name = next(n for n in zf.namelist() if n.endswith(".rm"))
    Path("/tmp/_spike.rm").write_bytes(zf.read(rm_name))

highlight = None
lines = []
with open("/tmp/_spike.rm", "rb") as f:
    for b in read_blocks(f):
        val = getattr(getattr(b, "item", None), "value", None)
        if isinstance(val, GlyphRange) and getattr(val, "rectangles", None) and highlight is None:
            highlight = val
        elif isinstance(val, Line) and getattr(val, "points", None):
            lines.append(val)

writer = PdfWriter()
writer.append(reader)

# 1) text highlight
r = highlight.rectangles[0]
x0, y_top = to_pdf(r.x, r.y)
x1, y_bot = to_pdf(r.x + r.w, r.y + r.h)
hl = Highlight(
    rect=(x0, y_bot, x1, y_top),
    quad_points=ArrayObject(FloatObject(v) for v in (x0, y_top, x1, y_top, x0, y_bot, x1, y_bot)),
    highlight_color="ffd400",
)
hl[NameObject("/Contents")] = TextStringObject(highlight.text)
writer.add_annotation(page_number=0, annotation=hl)
print(f"highlight: {highlight.text!r}")

# 2) pen strokes -> /Ink WITH an /AP appearance stream so it actually paints
strokes = [[to_pdf(p.x, p.y) for p in ln.points] for ln in lines]
xs = [x for st in strokes for x, _ in st]
ys = [y for st in strokes for _, y in st]
minx, miny, maxx, maxy = min(xs), min(ys), max(xs), max(ys)

ink_list = ArrayObject()
draw = "1 J 1 j 1.5 w 0 0 0 RG\n"  # round caps/joins, 1.5pt, black stroke
for st in strokes:
    arr = ArrayObject()
    for x, y in st:
        arr.extend([FloatObject(x), FloatObject(y)])
    ink_list.append(arr)
    draw += f"{st[0][0]:.2f} {st[0][1]:.2f} m\n"
    for x, y in st[1:]:
        draw += f"{x:.2f} {y:.2f} l\n"
    draw += "S\n"

ap = DecodedStreamObject()
ap.set_data(draw.encode("latin-1"))
ap[NameObject("/Type")] = NameObject("/XObject")
ap[NameObject("/Subtype")] = NameObject("/Form")
ap[NameObject("/FormType")] = NumberObject(1)
ap[NameObject("/BBox")] = ArrayObject(
    [FloatObject(minx), FloatObject(miny), FloatObject(maxx), FloatObject(maxy)]
)
ap_ref = writer._add_object(ap)

ink = DictionaryObject()
ink[NameObject("/Type")] = NameObject("/Annot")
ink[NameObject("/Subtype")] = NameObject("/Ink")
ink[NameObject("/InkList")] = ink_list
ink[NameObject("/Rect")] = ArrayObject(
    [FloatObject(minx), FloatObject(miny), FloatObject(maxx), FloatObject(maxy)]
)
ink[NameObject("/C")] = ArrayObject([FloatObject(0), FloatObject(0), FloatObject(0)])
ink[NameObject("/F")] = NumberObject(4)  # Print flag
apd = DictionaryObject()
apd[NameObject("/N")] = ap_ref
ink[NameObject("/AP")] = apd
writer.add_annotation(page_number=0, annotation=ink)
print(f"ink: {len(strokes)} strokes, x[{minx:.0f}..{maxx:.0f}] y[{miny:.0f}..{maxy:.0f}]")

with open(OUT, "wb") as f:
    writer.write(f)
print(f"wrote {OUT}")
