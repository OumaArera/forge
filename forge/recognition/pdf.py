"""
Rendering a certificate as a PDF.

Drawn directly with reportlab's canvas rather than assembled from flowables.
A certificate is a fixed piece of layout, not a document that reflows, and the
canvas keeps that honest: every position is stated once, and there is no
template engine between the wording and the page.

Two constraints shaped the design.

**It has to be checkable.** The verification code and the URL that resolves it
are printed at the same weight as the recipient's name, because a certificate
whose verification is in six-point grey at the bottom is a certificate nobody
verifies. The ledger hash at issue is printed too, so a reader can tie the
document to a point in the record.

**It must not be mistaken for a University award.** FORGE issues nothing that
carries academic credit. The disclaimer is in the body of the certificate, in
readable type, not tucked into a footer.
"""

from __future__ import annotations

import io
import math
import secrets
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from reportlab.lib import pdfencrypt
from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas

from .outlines import draw_outlined, string_width

NAVY = HexColor("#0C2142")
NAVY_SOFT = HexColor("#143A75")
BRAND = HexColor("#1F6FE5")
EMBER = HexColor("#F59E0B")
INK = HexColor("#334155")
MUTED = HexColor("#64748B")
HAIRLINE = HexColor("#CBD5E1")

PAGE = landscape(A4)
WIDTH, HEIGHT = PAGE


def _centre(pdf: canvas.Canvas, text: str, y: float, font: str, size: float,
            colour) -> None:
    pdf.setFillColor(colour)
    pdf.setFont(font, size)
    pdf.drawCentredString(WIDTH / 2, y, text)


def _centred_paragraph(pdf: canvas.Canvas, text: str, y: float, *, font: str,
                       size: float, colour, max_width: float,
                       leading: float) -> float:
    """Draw wrapped, centred text. Returns the y of the last line drawn."""
    pdf.setFillColor(colour)
    pdf.setFont(font, size)
    for line in simpleSplit(text, font, size, max_width):
        pdf.drawCentredString(WIDTH / 2, y, line)
        y -= leading
    return y


LOGO_PATH = Path(settings.BASE_DIR) / "forge_logo.png"


@lru_cache(maxsize=1)
def _watermark() -> ImageReader | None:
    """
    The FORGE mark, prepared once for use as a watermark.

    Two things happen here and both matter. The source file is 1254px square,
    which reportlab embeds verbatim -- that alone took a 3 KB certificate to
    nearly a megabyte, on a document students will be emailing from a phone.
    It is downscaled to 420px, which is more than a watermark at 330pt needs.

    It is also faded into white in the image itself rather than by drawing a
    scrim over it. PDF image transparency is awkward to control from reportlab,
    and a scrim would wash out everything beneath it too. Compositing here
    means the mark sits behind the text at a fixed, gentle weight and nothing
    else is affected.

    Cached, because a page of certificates would otherwise redo it per render.
    """
    if not LOGO_PATH.exists():
        return None
    try:
        from PIL import Image

        with Image.open(LOGO_PATH) as source:
            logo = source.convert("RGBA")
            logo.thumbnail((460, 460), Image.LANCZOS)

            # Flattened onto white *before* fading. Blending the RGBA directly
            # and then dropping the alpha turns every transparent pixel into
            # grey, which prints the mark inside a visible rectangle -- the
            # logo's own shape is the whole point of using it.
            white = Image.new("RGB", logo.size, (255, 255, 255))
            flattened = white.copy()
            flattened.paste(logo, mask=logo.getchannel("A"))

            # 0.12 keeps the mark readable as a texture without competing with
            # the wording, which is what a reader is actually there for.
            return ImageReader(Image.blend(white, flattened, 0.12))
    except Exception:  # pragma: no cover - a bad logo must not fail a download
        return None


def _draw_security_layer(pdf: canvas.Canvas, certificate) -> None:
    """
    The background that makes a convincing forgery tedious.

    None of this is cryptography -- the verification code and the ledger hash
    are what actually prove a certificate is genuine. What this does is raise
    the cost of a *casual* forgery: somebody who retypes the wording in a word
    processor produces something that looks obviously different beside a real
    one, and somebody who photoshops a real certificate has to rebuild a
    background woven from the original holder's name.

    Three layers, in the order they are drawn:

    1. A large, very pale FORGE mark behind the centre of the page.
    2. A guilloche -- the interference lattice used on banknotes. Cheap to
       draw from a parametric curve, awkward to reproduce by eye.
    3. Microtext: the holder's name repeated at 3.4pt across the whole page.
       At a glance it reads as a grey texture; under magnification it names
       the holder. Changing the name on a stolen certificate means redrawing
       every line of it.
    """
    name = (certificate.recipient_name or "").strip() or "FORGE"

    # -- 1. the mark -------------------------------------------------------
    mark = _watermark()
    if mark is not None:
        size = 340
        pdf.drawImage(
            mark,
            WIDTH / 2 - size / 2,
            HEIGHT / 2 - size / 2 - 18,
            width=size,
            height=size,
            preserveAspectRatio=True,
        )

    # -- 2. the guilloche --------------------------------------------------
    pdf.saveState()
    pdf.setStrokeColor(Color(0.12, 0.29, 0.55, alpha=0.075))
    pdf.setLineWidth(0.35)
    centre_x, centre_y = WIDTH / 2, HEIGHT / 2 - 10
    for ring in range(34):
        path = pdf.beginPath()
        amplitude = 26 + ring * 1.4
        radius = 96 + ring * 5.2
        for step in range(0, 361, 4):
            angle = math.radians(step)
            wobble = amplitude * math.sin(7 * angle + ring * 0.42)
            x = centre_x + (radius + wobble) * math.cos(angle) * 1.55
            y = centre_y + (radius + wobble) * math.sin(angle) * 0.72
            if step == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        path.close()
        pdf.drawPath(path, stroke=1, fill=0)
    pdf.restoreState()

    # -- 3. the microtext --------------------------------------------------
    #
    # Outlined, not text. An earlier version drew this with `drawString`,
    # which meant the holder's name was still sitting in the file forty times
    # over -- `pdftotext` lifted it straight out, defeating the point of
    # outlining the printed name above.
    #
    # One row is drawn into a form XObject and then placed repeatedly. Drawing
    # ~4,000 outlined glyphs individually would add megabytes; referencing one
    # row forty times costs it once.
    unit = f"{name.upper()}  \u2022  FORGE  \u2022  "
    size = 3.4
    width_of_unit = string_width(unit, size)
    if width_of_unit <= 0:
        return
    line = unit * (int(WIDTH / width_of_unit) + 2)
    row_width = string_width(line, size)

    form_name = "forge-microtext-row"
    # The row is drawn inside the form with a solid colour; the transparency
    # is applied where the form is *placed*. An alpha carried on the fill
    # colour does not survive into a form XObject, which is why an earlier
    # version printed this at full strength and buried the certificate.
    pdf.beginForm(form_name, 0, -size, row_width, size * 1.4)
    pdf.setFillColor(HexColor("#1F4A8C"))
    draw_outlined(pdf, line, 0, 0, size)
    pdf.endForm()

    row = 34.0
    index = 0
    while row < HEIGHT - 26:
        # Every other row is offset, so the repeat does not form vertical
        # channels that would be easy to mask out.
        offset = -width_of_unit / 2 if index % 2 else 0
        pdf.saveState()
        pdf.setFillAlpha(0.07)
        pdf.translate(18 + offset, row)
        pdf.doForm(form_name)
        pdf.restoreState()
        row += 8.4
        index += 1


def _draw_name_microband(pdf: canvas.Canvas, certificate, y: float) -> None:
    """
    A tight band of the holder's name directly under their printed name.

    Separate from the page-wide microtext because this one is meant to be
    noticed: it sits where a forger would have to edit, and it repeats the
    exact string they would have to change.
    """
    name = (certificate.recipient_name or "").strip().upper()
    if not name:
        return

    pdf.saveState()
    pdf.setFillColor(HexColor("#1F4A8C"))
    pdf.setFillAlpha(0.32)
    size = 3.6
    unit = f"{name} \u00b7 "
    width_of_unit = string_width(unit, size)
    span = min(WIDTH - 220, 520)
    line = unit * (int(span / width_of_unit) + 1)
    # Trimmed to the band rather than clipped, so it never bleeds past the rule.
    while string_width(line, size) > span and len(line) > len(unit):
        line = line[: -len(unit)]
    draw_outlined(pdf, line, WIDTH / 2, y, size, centred=True)
    pdf.restoreState()


def _facts(certificate) -> list[tuple[str, str]]:
    """
    The three things a reader of a certificate actually wants to know.

    Everything here comes from the ledger. Nothing is asserted that a
    confirmed contribution does not already back.
    """
    from forge.contributions.models import LedgerEntry

    entries = LedgerEntry.objects.filter(contributor=certificate.user)
    if certificate.project_id:
        entries = entries.filter(project_id=certificate.project_id)

    count = entries.count()
    if not count:
        return []

    facts: list[tuple[str, str]] = []
    if certificate.project:
        facts.append(("Project", certificate.project.title))
    facts.append((
        "Confirmed contributions",
        f"{count} contribution{'s' if count != 1 else ''}",
    ))

    # Named, because "confirmed" means nothing without saying by whom.
    names: list[str] = []
    for entry in entries.order_by("sequence"):
        for attestation in (entry.payload or {}).get("attestations", []):
            if attestation.get("decision") == "confirm":
                name = attestation.get("attestor_name", "")
                if name and name not in names:
                    names.append(name)
    if names:
        facts.append(("Independently confirmed by", " and ".join(names[:2])))
    return facts[:3]


def render_certificate(certificate, *, issued_to: str = "", issued_at=None) -> bytes:
    """
    Return the certificate as PDF bytes.

    `issued_to` and `issued_at` stamp the copy with who took it and when, so a
    leaked or altered copy traces back to one download rather than to
    "somebody, at some point". Omitting them renders an unstamped copy, which
    is what the test suite and any preview should use.
    """
    buffer = io.BytesIO()

    # Permission flags. Advisory -- a compliant viewer honours them, and
    # `pdftotext` does not -- which is exactly why the fields a forger would
    # want are also drawn as outlines rather than text. Printing stays on:
    # the document is meant to be printed, and turning that off would punish
    # the holder without inconveniencing anybody else.
    encryption = pdfencrypt.StandardEncryption(
        userPassword="",
        ownerPassword=secrets.token_urlsafe(24),
        canPrint=1,
        canModify=0,
        canCopy=0,
        canAnnotate=0,
        strength=128,
    )
    pdf = canvas.Canvas(buffer, pagesize=PAGE, encrypt=encryption)
    pdf.setTitle(f"FORGE {certificate.get_kind_display()} — {certificate.recipient_name}")
    pdf.setAuthor("FORGE, The Open University of Kenya")
    pdf.setSubject("Record of confirmed contribution. Not an academic award.")

    # -- frame ------------------------------------------------------------
    pdf.setFillColor(HexColor("#FFFFFF"))
    pdf.rect(0, 0, WIDTH, HEIGHT, fill=1, stroke=0)

    # Everything that makes a forgery expensive goes down first, so the
    # readable content sits on top of it.
    _draw_security_layer(pdf, certificate)

    # A navy band across the top, with a thin amber rule under it. The amber
    # is the one thing on the page that means "earned", used nowhere else.
    pdf.setFillColor(NAVY)
    pdf.rect(0, HEIGHT - 86, WIDTH, 86, fill=1, stroke=0)
    pdf.setFillColor(EMBER)
    pdf.rect(0, HEIGHT - 90, WIDTH, 4, fill=1, stroke=0)

    pdf.setFillColor(HexColor("#FFFFFF"))
    pdf.setFont("Helvetica-Bold", 26)
    pdf.drawString(56, HEIGHT - 54, "FORGE")
    # Measured rather than guessed: a fixed offset collided with the wordmark.
    pdf.setFont("Helvetica", 11)
    pdf.setFillColor(HexColor("#9CC0EC"))
    pdf.drawString(56 + pdf.stringWidth("FORGE", "Helvetica-Bold", 26) + 14,
                   HEIGHT - 54, "The Open University of Kenya")

    pdf.setFont("Helvetica", 9)
    pdf.drawRightString(WIDTH - 56, HEIGHT - 52,
                        "Don't just learn. Forge.")

    # A hairline border inset from the page edge.
    pdf.setStrokeColor(HAIRLINE)
    pdf.setLineWidth(0.75)
    pdf.rect(28, 28, WIDTH - 56, HEIGHT - 118, fill=0, stroke=1)

    # -- body -------------------------------------------------------------
    y = HEIGHT - 150
    _centre(pdf, certificate.get_kind_display().upper(), y, "Helvetica-Bold", 11, BRAND)

    y -= 16
    pdf.setStrokeColor(EMBER)
    pdf.setLineWidth(2)
    pdf.line(WIDTH / 2 - 26, y, WIDTH / 2 + 26, y)

    y -= 44
    _centre(pdf, "This is to record that", y, "Helvetica", 13, MUTED)

    # The recipient's name, sized down if it is long rather than clipped.
    # Outlined, not text: select-all and copy must not lift the holder's name.
    y -= 46
    name = certificate.recipient_name
    size = 36
    while string_width(name, size) > WIDTH - 200 and size > 18:
        size -= 2
    pdf.setFillColor(NAVY)
    drawn = draw_outlined(pdf, name, WIDTH / 2, y, size, centred=True)

    y -= 14
    pdf.setStrokeColor(HAIRLINE)
    pdf.setLineWidth(0.75)
    half = min(drawn / 2 + 40, WIDTH / 2 - 70)
    pdf.line(WIDTH / 2 - half, y, WIDTH / 2 + half, y)

    _draw_name_microband(pdf, certificate, y - 7)

    # The statement, minus the disclaimer sentence which is set apart below.
    statement = certificate.statement
    disclaimer = ""
    marker = "FORGE is a voluntary student initiative"
    if marker in statement:
        statement, disclaimer = statement.split(marker, 1)
        disclaimer = (marker + disclaimer).strip()
    statement = statement.strip()
    # The name already stands alone above, so it is not repeated in the body.
    if statement.startswith("This is to record that "):
        statement = statement[len("This is to record that "):]
    if statement.startswith(certificate.recipient_name):
        statement = statement[len(certificate.recipient_name):].lstrip()
        statement = statement[0].upper() + statement[1:] if statement else statement

    y -= 42
    y = _centred_paragraph(pdf, statement, y, font="Helvetica", size=13,
                           colour=INK, max_width=WIDTH - 240, leading=21)

    # -- what is actually being recorded ----------------------------------
    # The blank middle of a certificate is where a reader looks for substance.
    # These are facts drawn from the record, not decoration.
    facts = _facts(certificate)
    if facts:
        y -= 40
        column = (WIDTH - 200) / len(facts)
        left = 100
        pdf.setStrokeColor(HAIRLINE)
        pdf.setLineWidth(0.5)
        for index, (label, value) in enumerate(facts):
            centre_x = left + column * index + column / 2
            if index:
                pdf.line(left + column * index, y - 6, left + column * index, y + 26)
            pdf.setFillColor(MUTED)
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawCentredString(centre_x, y + 16, label.upper())
            pdf.setFillColor(NAVY_SOFT)
            size = 12.5
            while string_width(value, size) > column - 30 and size > 7:
                size -= 0.5
            draw_outlined(pdf, value, centre_x, y, size, centred=True)
        y -= 18

    if disclaimer:
        y -= 20
        _centred_paragraph(pdf, disclaimer, y, font="Helvetica-Oblique", size=9.5,
                           colour=MUTED, max_width=WIDTH - 280, leading=14)

    # -- footer -----------------------------------------------------------
    base = 66
    pdf.setStrokeColor(HAIRLINE)
    pdf.setLineWidth(0.75)
    pdf.line(56, base + 46, WIDTH - 56, base + 46)

    issued: datetime = certificate.issued_at
    pdf.setFont("Helvetica-Bold", 8.5)
    pdf.setFillColor(MUTED)
    pdf.drawString(56, base + 28, "ISSUED")
    pdf.setFont("Helvetica", 11)
    pdf.setFillColor(NAVY)
    pdf.drawString(56, base + 12, issued.strftime("%d %B %Y"))

    pdf.setFont("Helvetica-Bold", 8.5)
    pdf.setFillColor(MUTED)
    pdf.drawCentredString(WIDTH / 2, base + 28, "VERIFICATION CODE")
    pdf.setFillColor(NAVY)
    draw_outlined(pdf, certificate.verification_code, WIDTH / 2, base + 10, 14.5,
                  centred=True)

    pdf.setFont("Helvetica-Bold", 8.5)
    pdf.setFillColor(MUTED)
    pdf.drawRightString(WIDTH - 56, base + 28, "CHECK IT YOURSELF")
    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(BRAND)
    pdf.drawRightString(
        WIDTH - 56, base + 12,
        f"{settings.FRONTEND_BASE_URL.replace('https://', '').replace('http://', '')}"
        f"/verify-certificate",
    )

    pdf.setFont("Helvetica", 7.5)
    pdf.setFillColor(Color(0.55, 0.6, 0.68))
    tail = "Anyone can check this code without an account."
    if certificate.ledger_head:
        tail += f"   Ledger at issue: {certificate.ledger_head[:24]}…"
    pdf.drawCentredString(WIDTH / 2, 40, tail)

    if issued_to or issued_at:
        # Each downloaded copy carries the moment it was taken. Small, but not
        # hidden: a reader comparing two copies can see they are different
        # downloads, and the holder can tell which one got out.
        stamp_at = issued_at or datetime.now()
        stamp = f"Copy issued {stamp_at:%d %b %Y at %H:%M}"
        if issued_to:
            stamp += f" to {issued_to}"
        # Outlined as well: it names the holder, and the whole point of
        # outlining the name above is that it cannot be lifted out.
        pdf.saveState()
        pdf.setFillColor(Color(0.55, 0.6, 0.68))
        draw_outlined(pdf, stamp, 56, 30, 6.5, bold=False)
        pdf.restoreState()

    if certificate.revoked_at:
        # A revoked certificate still renders, so that somebody holding a copy
        # can see that it has been withdrawn rather than wondering why the
        # code no longer resolves.
        pdf.saveState()
        pdf.translate(WIDTH / 2, HEIGHT / 2)
        pdf.rotate(28)
        pdf.setFillColor(Color(0.86, 0.15, 0.15, alpha=0.18))
        pdf.setFont("Helvetica-Bold", 96)
        pdf.drawCentredString(0, 0, "REVOKED")
        pdf.restoreState()

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
