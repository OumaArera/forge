"""
Drawing text as vector outlines instead of text.

A PDF drawn with `drawString` carries the characters as text. That is normally
the right thing — it is searchable, it can be read aloud, and it copies
cleanly. On a certificate it is the opposite of what is wanted: select-all and
copy lifts the holder's name, the verification code and the confirming parties
straight out, which is most of the work of building a convincing forgery.

Permission flags help (see `pdf.py`), but they are advisory: a compliant viewer
honours them and `pdftotext` does not. Outlines are not advisory. The glyphs
become filled paths with no character codes behind them, so there is nothing
to extract however the file is opened.

**The cost is real and worth stating.** Outlined text cannot be read by a
screen reader and cannot be searched. So only the fields a forger would need
are outlined — the name, the code, the confirming parties. The statement and
the disclaimer stay as real text, because a reader who needs assistive
technology should still be able to hear what the document says and, above all,
that it carries no academic credit.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont


@lru_cache(maxsize=4)
def _load(path: str) -> tuple[TTFont, dict, int]:
    font = TTFont(path, fontNumber=0, lazy=True)
    glyphs = font.getGlyphSet()
    units = font["head"].unitsPerEm
    return font, glyphs, units


class _CanvasPen(BasePen):
    """
    Replays a glyph onto a reportlab path.

    TrueType curves are quadratic and PDF paths are cubic, so `qCurveTo` is
    converted exactly rather than approximated: for a quadratic with endpoints
    P0, P2 and control Q, the equivalent cubic controls are
    P0 + 2/3(Q - P0) and P2 + 2/3(Q - P2).
    """

    def __init__(self, glyph_set, path, scale: float, x: float, y: float):
        super().__init__(glyph_set)
        self.path = path
        self.scale = scale
        self.dx = x
        self.dy = y
        self._start = None

    def _pt(self, point):
        return (self.dx + point[0] * self.scale, self.dy + point[1] * self.scale)

    def _moveTo(self, pt):
        self._start = pt
        x, y = self._pt(pt)
        self.path.moveTo(x, y)

    def _lineTo(self, pt):
        x, y = self._pt(pt)
        self.path.lineTo(x, y)

    def _curveToOne(self, pt1, pt2, pt3):
        (x1, y1), (x2, y2), (x3, y3) = self._pt(pt1), self._pt(pt2), self._pt(pt3)
        self.path.curveTo(x1, y1, x2, y2, x3, y3)

    def _qCurveToOne(self, pt1, pt2):
        # BasePen normally decomposes quadratics for us, but doing it here
        # keeps the conversion exact rather than flattened into line segments.
        x0, y0 = self._pt(self._getCurrentPoint())
        qx, qy = self._pt(pt1)
        x2, y2 = self._pt(pt2)
        c1 = (x0 + 2 / 3 * (qx - x0), y0 + 2 / 3 * (qy - y0))
        c2 = (x2 + 2 / 3 * (qx - x2), y2 + 2 / 3 * (qy - y2))
        self.path.curveTo(c1[0], c1[1], c2[0], c2[1], x2, y2)

    def _closePath(self):
        self.path.close()


@lru_cache(maxsize=2)
def _font_path(bold: bool) -> str:
    """
    The bold or regular face reportlab already ships.

    Using the bundled font rather than a system one keeps rendering identical
    on a developer's laptop and on the server, which matters when the output
    is a document people compare by eye.

    Resolved from the `reportlab` package rather than `reportlab.fonts`:
    the latter is a namespace package whose `__file__` is None.
    """
    import reportlab

    directory = Path(reportlab.__file__).parent / "fonts"
    return str(directory / ("VeraBd.ttf" if bold else "Vera.ttf"))


def string_width(text: str, size: float, *, bold: bool = True) -> float:
    """Advance width of `text` at `size`, in points."""
    _, glyphs, units = _load(_font_path(bold))
    cmap = _load(_font_path(bold))[0].getBestCmap()
    scale = size / units
    total = 0.0
    for character in text:
        name = cmap.get(ord(character))
        if name is None:
            name = cmap.get(ord(" "))
        if name is None:
            continue
        total += glyphs[name].width * scale
    return total


def draw_outlined(
    pdf,
    text: str,
    x: float,
    y: float,
    size: float,
    *,
    bold: bool = True,
    centred: bool = False,
) -> float:
    """
    Draw `text` as filled vector paths. Returns the width drawn.

    The caller sets the fill colour beforehand, exactly as with `drawString`.
    """
    if not text:
        return 0.0

    path_file = _font_path(bold)
    font, glyphs, units = _load(path_file)
    cmap = font.getBestCmap()
    scale = size / units

    width = string_width(text, size, bold=bold)
    cursor = x - width / 2 if centred else x

    for character in text:
        name = cmap.get(ord(character))
        if name is None:
            cursor += size * 0.3
            continue
        glyph = glyphs[name]
        # A space has an advance but no contours; skipping the path avoids
        # emitting an empty path object per space.
        if character != " ":
            path = pdf.beginPath()
            glyph.draw(_CanvasPen(glyphs, path, scale, cursor, y))
            pdf.drawPath(path, fill=1, stroke=0)
        cursor += glyph.width * scale

    return width
