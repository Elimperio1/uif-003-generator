"""
UI-19 PDF writer: the standalone script's pdf_writer.py, returning bytes.

Stamps employer and employee data onto the official UI-19 form
(assets/UI19_official.pdf) at the coordinates measured in
assets/ui19_layout.json, then merges that overlay onto a copy of the form.
Behaviour matches the script: 6 rows a page with the employer block repeated,
"(Page X of Y)" when there is more than one page, the full UIF reference
allowed to overflow its boxes, and the signature left blank.
"""

from __future__ import annotations

import datetime as dt
import io
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from .ui19 import FormRow

ASSETS = Path(__file__).resolve().parent / "assets"
BASE_PDF = ASSETS / "UI19_official.pdf"
LAYOUT_FILE = ASSETS / "ui19_layout.json"

FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"


@dataclass
class Employer:
    """Employer block of the form (the script's employer_config.json)."""

    uif_employer_ref: str
    trading_name: str
    branch_no: str = ""
    paye_ref: str = ""
    cipro_no: str = ""
    physical_address: str = ""
    work_address: str = ""
    postal_address: str = ""
    email: str = ""
    fax_no: str = ""
    phone_no: str = ""
    authorised_person: str = ""
    declaration_employer_name: str = ""
    declaration_employer_id_number: str = ""


@lru_cache(maxsize=1)
def load_layout() -> dict:
    return json.loads(LAYOUT_FILE.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _base_pdf_bytes() -> bytes:
    return BASE_PDF.read_bytes()


def _y(layout, top_or_bottom):
    """Convert a pdfplumber top-down coordinate to a reportlab bottom-up one."""
    return layout["page_height"] - top_or_bottom


def _draw_text_in_box(c, text, x0, x1, top, bottom, layout, size=8, align="left", font=FONT):
    if not text:
        return
    c.setFont(font, size)
    baseline = _y(layout, bottom) + 2.6
    if align == "left":
        c.drawString(x0 + 2, baseline, str(text))
    elif align == "center":
        c.drawCentredString((x0 + x1) / 2, baseline, str(text))


def _draw_digits_in_boxes(c, value, box_edges, top, bottom, layout, size=9, font=FONT,
                          allow_overflow=False):
    """Each character goes into the next box. Extra characters are dropped
    unless allow_overflow, which keeps drawing past the last box at the same
    box width (a UIF reference like 0000000/0 is wider than its boxes, and the
    whole number being legible wins over staying inside the lines)."""
    if not value:
        return
    chars = str(value)
    n_boxes = len(box_edges) - 1
    c.setFont(font, size)
    baseline = _y(layout, bottom) + 2.6
    box_w = box_edges[-1] - box_edges[-2]
    n_draw = len(chars) if allow_overflow else min(len(chars), n_boxes)
    for i in range(n_draw):
        if i < n_boxes:
            x0, x1 = box_edges[i], box_edges[i + 1]
        else:
            x0 = box_edges[-1] + (i - n_boxes) * box_w
            x1 = x0 + box_w
        c.drawCentredString((x0 + x1) / 2, baseline, chars[i])


def _fmt_date_ddmmyy(yyyymmdd: str) -> str:
    if len(yyyymmdd) != 8:
        return ""
    return f"{yyyymmdd[6:8]}{yyyymmdd[4:6]}{yyyymmdd[2:4]}"


def _fmt_money(v):
    if v is None:
        return "", ""
    rand = int(v)
    cents = int(round((v - rand) * 100))
    return f"{rand:,}", f"{cents:02d}"


def _make_overlay_page(layout, employer: Employer, rows: list[FormRow], month_label,
                       page_no, total_pages, today_str):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(layout["page_width"], layout["page_height"]))

    # The month/year in the form's own box next to "...for the month".
    mb = layout["month_box"]
    _draw_text_in_box(c, month_label, mb["x0"], mb["x1"], mb["top"], mb["bottom"], layout,
                      size=9, align="center", font=FONT_BOLD)

    if total_pages > 1:
        note_area = layout["header_note_area"]
        c.setFont(FONT, 7)
        c.drawString(note_area["x0"], _y(layout, note_area["top"] + 8),
                     f"(Page {page_no} of {total_pages})")

    for key, box in layout["employer_text_fields"].items():
        _draw_text_in_box(c, getattr(employer, key, ""), box["x0"], box["x1"],
                          box["top"], box["bottom"], layout, size=7.5)

    df = layout["employer_digit_fields"]
    _draw_digits_in_boxes(c, employer.uif_employer_ref.replace(" ", ""),
                          df["uif_employer_ref"]["boxes"], df["uif_employer_ref"]["top"],
                          df["uif_employer_ref"]["bottom"], layout, size=8, allow_overflow=True)
    _draw_digits_in_boxes(c, employer.branch_no, df["branch_no"]["boxes"],
                          df["branch_no"]["top"], df["branch_no"]["bottom"], layout)
    _draw_digits_in_boxes(c, employer.paye_ref, df["paye_ref"]["boxes"],
                          df["paye_ref"]["top"], df["paye_ref"]["bottom"], layout)
    _draw_digits_in_boxes(c, employer.cipro_no, df["cipro_no"]["boxes"],
                          df["cipro_no"]["top"], df["cipro_no"]["bottom"], layout)

    tbl = layout["table"]
    cols = tbl["column_bounds"]
    row_tops = tbl["row_tops"]
    row_h = tbl["row_height"]
    r_split = cols["gross_remuneration_split"]
    # The last row's real bottom border sits just above the declaration line.
    declaration_top = layout["declaration"]["employer_name_blank"]["top"]
    row_bottoms = [row_tops[i + 1] if i + 1 < len(row_tops)
                   else min(row_tops[i] + row_h, declaration_top - 1.0)
                   for i in range(len(row_tops))]

    for i, row in enumerate(rows):
        top, bottom = row_tops[i], row_bottoms[i]

        b = cols["surname"]
        _draw_text_in_box(c, row.surname, b[0], b[1], top, bottom, layout, size=7)
        b = cols["initials"]
        _draw_text_in_box(c, row.initials, b[0], b[1], top, bottom, layout, size=7)

        _draw_digits_in_boxes(c, row.id_number, tbl["id_number_boxes"], top, bottom, layout,
                              size=7.5)

        rand_str, cents_str = _fmt_money(row.gross)
        gb = cols["gross_remuneration"]
        _draw_text_in_box(c, rand_str, gb[0], r_split, top, bottom, layout, size=6.5,
                          align="center")
        _draw_text_in_box(c, cents_str, r_split, gb[1], top, bottom, layout, size=6.5,
                          align="center")

        b = cols["hours_worked"]
        hours_val = "" if row.hours_worked is None else (
            str(int(row.hours_worked)) if float(row.hours_worked).is_integer()
            else str(row.hours_worked))
        _draw_text_in_box(c, hours_val, b[0], b[1], top, bottom, layout, size=7, align="center")

        _draw_digits_in_boxes(c, _fmt_date_ddmmyy(row.commencement_date),
                              tbl["commencement_date_boxes"], top, bottom, layout, size=6.5)
        _draw_digits_in_boxes(c, _fmt_date_ddmmyy(row.termination_date),
                              tbl["termination_date_boxes"], top, bottom, layout, size=6.5)

        b = cols["termination_reason_code"]
        _draw_text_in_box(c, row.termination_reason_code, b[0], b[1], top, bottom, layout,
                          size=6.5, align="center")
        b = cols["uif_contributor"]
        _draw_text_in_box(c, row.uif_contributor, b[0], b[1], top, bottom, layout, size=7,
                          align="center")
        b = cols["non_contributor_reason_code"]
        _draw_text_in_box(c, row.non_contributor_reason_code, b[0], b[1], top, bottom, layout,
                          size=6.5, align="center")

    decl = layout["declaration"]
    b = decl["employer_name_blank"]
    _draw_text_in_box(c, employer.declaration_employer_name, b["x0"], b["x1"], b["top"],
                      b["bottom"], layout, size=8)
    b = decl["employer_id_blank"]
    _draw_text_in_box(c, employer.declaration_employer_id_number, b["x0"], b["x1"], b["top"],
                      b["bottom"], layout, size=8)
    b = decl["date_blank"]
    _draw_text_in_box(c, today_str, b["x0"], b["x1"], b["top"], b["bottom"], layout, size=8)
    # Signature intentionally left blank: sign the printed/PDF copy by hand.

    c.save()
    buf.seek(0)
    return buf


def write_pdf(employer: Employer, rows: list[FormRow], month_label: str,
              today: dt.date | None = None) -> bytes:
    """The filled UI-19 as PDF bytes, one form page per 6 employees."""
    layout = load_layout()
    today_str = (today or dt.date.today()).strftime("%d/%m/%Y")
    rows_per_page = layout["table"]["rows_per_page"]
    batches = [rows[i:i + rows_per_page] for i in range(0, len(rows), rows_per_page)] or [[]]
    total_pages = len(batches)

    writer = PdfWriter()
    for page_no, batch in enumerate(batches, start=1):
        overlay = PdfReader(_make_overlay_page(layout, employer, batch, month_label, page_no,
                                               total_pages, today_str))
        # A fresh blank form per page: pages added from one reader share their
        # content stream, so every merge would land on every page.
        blank = PdfReader(io.BytesIO(_base_pdf_bytes())).pages[0]
        page = writer.add_page(blank)
        page.merge_page(overlay.pages[0])

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
