"""Tests for the UI-19 PDF writer."""

import datetime as dt
import io

from pypdf import PdfReader

from uif import ui19_pdf
from uif.ui19 import FormRow

EMPLOYER = ui19_pdf.Employer(uif_employer_ref="1234567/8", trading_name="Acme (Pty) Ltd")


def row(n):
    return FormRow(str(n), f"Surname{n}", "J.", "8306056177085", 5139.10, 173.33,
                   "20200101", "", "YES")


def pdf(rows, label="May 2025"):
    data = ui19_pdf.write_pdf(EMPLOYER, rows, label, dt.date(2025, 6, 3))
    return PdfReader(io.BytesIO(data))


def placed_text(page):
    """[(text, x, y)] for every text run on the page, in PDF user space."""
    found = []

    def visitor(text, cm, tm, _font, _size):
        if text.strip():
            x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
            y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
            found.append((text.strip(), x, y))

    page.extract_text(visitor_text=visitor)
    return found


def test_six_rows_per_page():
    assert len(pdf([row(n) for n in range(6)]).pages) == 1
    assert len(pdf([row(n) for n in range(7)]).pages) == 2
    assert len(pdf([]).pages) == 1


def test_each_page_carries_only_its_own_rows():
    first, second = pdf([row(n) for n in range(7)]).pages
    first_text, second_text = first.extract_text(), second.extract_text()
    assert "Surname0" in first_text and "Surname6" not in first_text
    assert "Surname6" in second_text and "Surname0" not in second_text


def test_values_land_in_their_boxes():
    layout = ui19_pdf.load_layout()
    height = layout["page_height"]
    texts = placed_text(pdf([row(1)]).pages[0])

    surname = [(x, y) for t, x, y in texts if t == "Surname1"]
    assert surname, texts
    x, y = surname[0]
    left, right = layout["table"]["column_bounds"]["surname"]
    top, next_top = layout["table"]["row_tops"][0], layout["table"]["row_tops"][1]
    assert left <= x <= right
    assert height - next_top <= y <= height - top

    month = [x for t, x, _ in texts if t == "May 2025"]
    assert month, texts
    assert layout["month_box"]["x0"] <= month[0] <= layout["month_box"]["x1"]

    assert any(t == "03/06/2025" for t, _, _ in texts)       # declaration date
    assert any(t == "5,139" for t, _, _ in texts)            # rand part of gross
    assert any(t == "Acme (Pty) Ltd" for t, _, _ in texts)


def test_page_note_only_when_multiple_pages():
    single = [t for t, _, _ in placed_text(pdf([row(1)]).pages[0])]
    assert not any("Page 1 of" in t for t in single)
    second = [t for t, _, _ in placed_text(pdf([row(n) for n in range(7)]).pages[1])]
    assert any("(Page 2 of 2)" in t for t in second)
