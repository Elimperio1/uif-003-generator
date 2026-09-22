"""Tests for the Sage PDF report readers (ported from the standalone UI19 script)."""

import pytest

from tests import sage_pdf_fixtures as fx
from uif import parse_sage_pdf, ui19


def test_is_pdf():
    assert parse_sage_pdf.is_pdf(fx.blank_pdf())
    assert not parse_sage_pdf.is_pdf(b"Employee code:,32\r\n")


@pytest.mark.parametrize("builder, kind", [
    (fx.ytd_pdf, "ytd"),
    (fx.employee_details_pdf, "employee_details"),
    (fx.company_details_pdf, "company_details"),
    (fx.blank_pdf, None),
])
def test_report_kind(builder, kind):
    assert parse_sage_pdf.report_kind(builder()) == kind


def test_report_kind_of_garbage_is_none():
    assert parse_sage_pdf.report_kind(b"%PDF-1.4 not really") is None


def test_ytd_records():
    records, warnings = parse_sage_pdf.parse_ytd(fx.ytd_pdf())
    # Report order, codes exactly as printed: Sage treats "007" and "0007" as
    # different employees, so they must not be normalised together.
    assert list(records) == ["007", "12", "0007"]
    assert warnings == []
    assert records["0007"].employee_name == "Sam Other"

    jane = records["007"]
    assert jane.employee_name == "Jane Sample"
    assert jane.status == "Employed"
    assert jane.start_date == "20200101"
    assert jane.end_date == ""
    assert jane.gross("March") == 5139.10
    assert jane.gross("May") == 5300.00
    assert jane.gross("June") == 0.0
    assert jane.uif_deducted["March"] == 51.39  # Deductions, not Company Contributions
    assert jane.uif_deducted["February"] == 0.0

    leaver = records["12"]
    assert leaver.status == "No longer employed"
    assert leaver.start_date == "20240301"
    assert leaver.end_date == "20240515"
    assert leaver.uif_deducted == {}  # no UIF deduction line on the page


def test_ytd_tax_year_end():
    assert parse_sage_pdf.tax_year_end_year(fx.ytd_pdf()) == 2025


def test_ytd_tax_year_end_from_midyear_print():
    """A period ending in August 2026 belongs to the tax year ending Feb 2027."""
    assert parse_sage_pdf.tax_year_end_year(fx.ytd_pdf("2026/08/31")) == 2027


def test_ytd_rejects_non_ytd_pdf():
    with pytest.raises(ValueError):
        parse_sage_pdf.parse_ytd(fx.employee_details_pdf())


def test_employee_details_records():
    records = parse_sage_pdf.parse_employees(fx.employee_details_pdf())
    assert list(records) == ["007", "12"]

    jane = records["007"]
    assert jane.employee_name == "Ms J Sample"
    assert jane.surname == "Sample"
    assert jane.id_number == "8306056177085"
    assert jane.passport_number == ""
    assert jane.date_engaged == "20200101"
    assert jane.end_date == ""
    assert jane.uif_status == "Contributes"
    assert jane.average_hours == 173.33  # comma decimal

    leaver = records["12"]
    assert leaver.surname == "Van de Rheede"
    assert leaver.id_number == ""
    assert leaver.passport_number == "BN487879"
    assert leaver.end_date == "20240515"
    assert leaver.uif_status == "Does not contribute"
    assert leaver.average_hours is None


def test_company_details_fields():
    fields = parse_sage_pdf.parse_company(fx.company_details_pdf())
    assert fields == {
        "trading_name": "Sample Co (Pty) Ltd",
        "cipro_no": "2001/123456/07",
        "paye_ref": "7123456789",
        "uif_ref": "1234567/8",
        "physical_address": "1 Main Road, Paarl",
        "postal_address": "PO Box 1, Paarl",
        # The UIF contact (right column), never the SARS contact on the left.
        "contact_name": "Right Person",
        "email_header": "uif@example.com",
        "contact_phone": "0211111111",
    }


def test_pdf_reports_feed_the_ui19_rules():
    ytd, _ = parse_sage_pdf.parse_ytd(fx.ytd_pdf())
    employees = parse_sage_pdf.parse_employees(fx.employee_details_pdf())

    rows, _ = ui19.form_rows(ytd, employees, "May", "202405")
    by_code = {r.employee_code: r for r in rows}
    assert by_code["007"].gross == 5300.00
    assert by_code["007"].uif_contributor == "YES"
    assert by_code["007"].hours_worked == 173.33
    # "0007" is not on the Employee Details report: YTD name and UIF line only.
    assert (by_code["0007"].surname, by_code["0007"].gross) == ("Other", 4000.00)
    assert by_code["0007"].id_number == ""
    # Leaves in May with R0.00 that month: still declared, UIF status from the report.
    assert by_code["12"].gross == 0.0
    assert by_code["12"].termination_date == "20240515"
    assert by_code["12"].uif_contributor == "NO"
    assert by_code["12"].id_number == "BN487879"
    assert (by_code["12"].surname, by_code["12"].initials) == ("Van de Rheede", "L.")

    rows, _ = ui19.form_rows(ytd, employees, "June", "202406")
    assert [r.employee_code for r in rows] == []  # nobody paid, nobody starting or leaving
