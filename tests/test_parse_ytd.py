"""Unit tests for uif.parse_ytd."""

from uif.parse_ytd import (
    _num,
    _parse_status,
    _slash_date_to_yyyymmdd,
    parse,
    tax_year_end_year,
)

# A minimal YTD CSV with the same shape as a real Sage export: title lines,
# the irregular month-header row, and one employee block. The non-breaking
# space (\xa0) is the real thousands separator Sage uses.
SAMPLE_YTD = (
    "Year to Date Detail,,,,,,,,,,,,,,,,,,\r\n"
    "Printed for period ending 2025/02/28,,,,,,,,,,,,,,,,,,\r\n"
    "Printed for Test Company: Cycle,,,,,,,,,,,,,,,,,,\r\n"
    " ,,March,,April,,,May,June,July,August,September,October,November,,December,January,February,Total\r\n"
    "Employee code:,7,,Employee name:,,Jane Sample,,,,,,,,,,,,,\r\n"
    ",,,,,,Status: No longer employed; From: 2020/01/01 To: 2024/12/24; Tax age: 40,,,,,,,,,,,,\r\n"
    "Earnings,,,,,,,,,,,,,,,,,,\r\n"
    "Basic salary,,1\xa0000.00,,0,,,0,0,0,0,0,0,0,,0,2\xa0000.00,0,3\xa0000.00\r\n"
    "Travel allowance - 80%,,500,,0,,,0,0,0,0,0,0,0,,0,0,0,500\r\n"
    "TOTAL,,1\xa0500.00,,0,,,0,0,0,0,0,0,0,,0,2\xa0000.00,0,3\xa0500.00\r\n"
    "Deductions,,,,,,,,,,,,,,,,,,\r\n"
    "Unemployment insurance fund,,14.00,,0,,,0,0,0,0,0,0,0,,0,20.00,0,34.00\r\n"
    "TOTAL,,14.00,,0,,,0,0,0,0,0,0,0,,0,20.00,0,34.00\r\n"
    "REPORT SUMMARY,,,,,,,,,,,,,,,,,,\r\n"
)


def test_num_handles_nbsp_thousands_separator():
    assert _num("6\xa0187.50") == 6187.50


def test_num_handles_blank_zero_and_negative():
    assert _num("") == 0.0
    assert _num("0") == 0.0
    assert _num("-85.15") == -85.15


def test_slash_date_conversion():
    assert _slash_date_to_yyyymmdd("2023/12/31") == "20231231"
    assert _slash_date_to_yyyymmdd("no date here") == ""


def test_parse_status_extracts_status_and_end_date():
    status, end_date = _parse_status(
        "Status: No longer employed; From: 2019/03/01 To: 2023/12/31; Tax age: 28"
    )
    assert status == "No longer employed"
    assert end_date == "20231231"


def test_parse_status_employed_has_no_end_date():
    status, end_date = _parse_status("Status: Employed; From: 2023/08/24; Tax age: 41")
    assert status == "Employed"
    assert end_date == ""


def test_tax_year_end_year():
    assert tax_year_end_year(SAMPLE_YTD.encode("cp1252")) == 2025


def test_parse_reads_employee_block_and_earnings():
    records = parse(SAMPLE_YTD.encode("cp1252"))
    assert set(records) == {"7"}

    record = records["7"]
    assert record.employee_name == "Jane Sample"
    assert record.status == "No longer employed"
    assert record.end_date == "20241224"

    # March: basic 1000 + travel 500
    assert record.gross("March") == 1500.0
    # remunerable: 1000 + 0.8 * 500
    assert record.remunerable("March") == 1400.0
    # January: basic 2000 only
    assert record.gross("January") == 2000.0
    # February: nothing
    assert record.gross("February") == 0.0
