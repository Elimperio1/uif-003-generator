"""Tests for the Standard Format xlsx parsers."""

from uif import parse_standard

from tests.standard_fixtures import (
    build_master_workbook,
    build_master_workbook_duplicate_code,
    build_payroll_workbook,
    build_payroll_workbook_duplicate_code,
    build_payroll_workbook_missing_month,
    build_payroll_workbook_trailing_empty_block,
)


def test_detect_format():
    # xlsx files are zip archives and start with the PK magic.
    assert parse_standard.detect_format(b"PK\x03\x04rest-of-zip") == "standard"
    assert parse_standard.detect_format(b"Employee code:,32\r\n") == "sage"
    assert parse_standard.detect_format(b"") == "sage"


def test_list_year_sheets_filters_and_sorts():
    assert parse_standard.list_year_sheets(build_payroll_workbook()) == ["2023", "2025"]


def test_tax_year_end_year():
    assert parse_standard.tax_year_end_year("2025") == 2025
    assert parse_standard.tax_year_end_year(" 2023 ") == 2023


def test_read_company_header():
    header = parse_standard.read_company_header(build_payroll_workbook(), "2023")
    assert header == {
        "company": "Acme Electrical (Pty) Ltd",
        "paye": "7012345678",
        "uif": "0123456/7",
    }


import io

import openpyxl
import pytest


def test_parse_employees_reads_master_sheet():
    records = parse_standard.parse_employees(build_master_workbook())
    assert sorted(records) == ["1", "2", "3", "9"]   # stub row 010 skipped

    botha = records["1"]
    assert botha.first_names == "Petrus"
    assert botha.surname == "Botha"
    assert botha.id_number == ""                      # not 13 digits
    assert botha.passport_number == "AB123456"
    assert botha.date_of_birth == "19790214"
    assert botha.date_engaged == "20180903"
    assert botha.end_date == ""
    assert botha.employee_status == "Normal"
    assert botha.uif_status == "Contributes"

    nkosi = records["2"]     # numeric ID cell + Excel datetime cells
    assert nkosi.id_number == "9103105023081"
    assert nkosi.passport_number == ""
    assert nkosi.date_of_birth == "19910310"
    assert nkosi.date_engaged == "20180403"

    fourie = records["3"]    # terminated
    assert fourie.end_date == "20221107"
    assert fourie.employee_status == "Terminated"

    vdwalt = records["9"]    # multi-word surname column survives whole
    assert vdwalt.surname == "Van Der Walt"
    assert vdwalt.first_names == "Willem"


def test_parse_employees_requires_master_sheet():
    wb = openpyxl.Workbook()
    wb.active.title = "Wrong name"
    buf = io.BytesIO()
    wb.save(buf)
    with pytest.raises(ValueError, match="Employee details"):
        parse_standard.parse_employees(buf.getvalue())


def test_parse_ytd_maps_months_by_position_not_label():
    records, _ = parse_standard.parse_ytd(build_payroll_workbook(), "2025")
    rec = records["1"]
    # Row 2 is labelled "10/2022" (stale) but is positionally April.
    assert rec.gross("April") == 8300.0
    assert rec.earnings["March"] == {"Salaris": 10000.0}
    assert rec.earnings["December"] == {
        "Salaris": 5500.0, "Leave pay": 5200.0, "Bonus": 4600.0,
    }
    assert rec.gross("December") == 15300.0
    assert rec.employee_name == "Petrus Johannes Botha"
    assert rec.status == "Employed"
    assert rec.end_date == ""


def test_parse_ytd_termination_and_death_warning():
    records, warnings = parse_standard.parse_ytd(build_payroll_workbook(), "2025")
    rec = records["2"]
    assert rec.status == "Terminated"
    assert rec.end_date == "20220405"
    assert any("Death" in w and "status 06" in w for w in warnings)


def test_parse_ytd_integrity_warnings():
    _, warnings = parse_standard.parse_ytd(build_payroll_workbook(), "2025")
    assert any("75.00" in w and "April" in w for w in warnings)         # UIF divergence
    assert any("Bruto salaris" in w and "May" in w for w in warnings)   # bruto mismatch
    assert not any("June" in w for w in warnings)                       # cap != divergence


def test_parse_ytd_rejects_wrong_month_count():
    with pytest.raises(ValueError, match="expected 12"):
        parse_standard.parse_ytd(build_payroll_workbook_missing_month(), "2024")


def test_parse_ytd_unknown_sheet():
    with pytest.raises(ValueError, match="2031"):
        parse_standard.parse_ytd(build_payroll_workbook(), "2031")


def test_parse_ytd_empty_employee_nr_ends_scan():
    records, _ = parse_standard.parse_ytd(
        build_payroll_workbook_trailing_empty_block(), "2024"
    )
    assert sorted(records) == ["1"]


def test_parse_ytd_duplicate_employee_code_raises():
    with pytest.raises(ValueError, match="more than once"):
        parse_standard.parse_ytd(build_payroll_workbook_duplicate_code(), "2024")


def test_parse_employees_duplicate_employee_number_raises():
    with pytest.raises(ValueError, match="more than once"):
        parse_standard.parse_employees(build_master_workbook_duplicate_code())


from uif.models import CONFIRMED_FULL_REMUNERABLE, REMUNERABLE_PCT


def test_standard_earning_names_are_confirmed_remunerable():
    for name in ("Salaris", "Leave pay", "Oortyd", "Bonus", "Verlof"):
        assert name in CONFIRMED_FULL_REMUNERABLE
    # Reistoelaag stays unknown on purpose: the existing "unknown earning
    # type" soft warning must fire if it ever carries a value.
    assert "Reistoelaag" not in CONFIRMED_FULL_REMUNERABLE
    assert "Reistoelaag" not in REMUNERABLE_PCT


from uif import generate_003, match, validate
from uif.models import Company


def test_standard_pair_through_existing_pipeline():
    ytd, _ = parse_standard.parse_ytd(build_payroll_workbook(), "2023")
    employees = parse_standard.parse_employees(build_master_workbook())
    matched, _ = match.join(ytd, employees)

    blocking, _ = validate.validate(matched, "February")
    assert blocking == []

    company = Company(
        uif_ref="012345678",
        paye_ref="7777777777",
        contact_name="Tester",
        contact_phone="0123456789",
        contact_email_header="tax@example.test",
        contact_email_footer="tax@example.test",
    )
    content = generate_003.build(matched, "February", "202302", company)
    lines = content.decode("latin-1").split("\r\n")

    assert lines[0].startswith('8000,"UICR"')
    assert "8070,202302" in lines[0]
    worker = lines[1]                          # only emp 001 earned in February
    assert '8210,"AB123456"' in worker        # passport, quoted
    assert '8230,"Botha"' in worker
    assert "8280,01" in worker
    assert "8300,6000,8310,6000,8320,120" in worker
    footer = lines[2]
    assert footer.startswith('8002,"UIEM"')
    assert "8150,1" in footer
