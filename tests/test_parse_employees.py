"""Unit tests for uif.parse_employees."""

from uif.parse_employees import (
    _clean_id,
    _ddmmyyyy_to_yyyymmdd,
    _strip_decimal_suffix,
    _surname_from_employee_name,
    parse,
)

SAMPLE_EMPLOYEES = (
    "Employee Details,,,,,,,,,,,,,,,,\r\n"
    "Printed for period ending 2025/02/28,,,,,,,,,,,,,,,,\r\n"
    "Printed for Test Company: Cycle,,,,,,,,,,,,,,,,\r\n"
    "Personal Details,,,,,,,,,,,,,,,,\r\n"
    "Employee code,7.00,,,,,,,,,,,,,,,\r\n"
    "Employee name,Mr J Sample,,,,,,,,,,,,,,,\r\n"
    "Full names,Jane ,,,,,,,,,,,,,,,\r\n"
    "Known as,Jane Sample,,,,,,,,,,,,,,,\r\n"
    "ID number,8306056177085.00,,,,,Date of birth,,05/06/1983,,Age,,41,,,,\r\n"
    "Passport number,,,,,,Passport country,,,,,,,,,,\r\n"
    "Date Engaged,,24/08/2023,,,,,End date,,,,,,,,,\r\n"
    "Tax status,,Statutory Tables,,,,,Employee status,,,,Normal,,,,,\r\n"
    "UIF status,,Contributes,,,,,,,,,,,,,,\r\n"
    "Personal Details,,,,,,,,,,,,,,,,\r\n"
    "Employee code,12.00,,,,,,,,,,,,,,,\r\n"
    "Employee name,R van Wyk,,,,,,,,,,,,,,,\r\n"
    "Full names,Rutha ,,,,,,,,,,,,,,,\r\n"
    "ID number,,,,,,Date of birth,,11/08/1974,,Age,,50,,,,\r\n"
    "Passport number,BN487879,,,,,Passport country,,Zimbabwe,,,,,,,,\r\n"
    "Date Engaged,,15/05/2022,,,,,End date,,24/12/2024,,,,,,,\r\n"
    "Tax status,,Statutory Tables,,,,,Employee status,,,,Terminated,,,,,\r\n"
    "UIF status,,Contributes,,,,,,,,,,,,,,\r\n"
)


def test_strip_decimal_suffix():
    assert _strip_decimal_suffix("32.00") == "32"
    assert _strip_decimal_suffix("8306056177085.00") == "8306056177085"


def test_clean_id_strips_suffix():
    assert _clean_id("8306056177085.00") == "8306056177085"


def test_clean_id_left_pads_lost_leading_zero():
    # Excel can drop a leading zero, turning a 13-digit ID into 12 digits.
    assert _clean_id("101166305082.00") == "0101166305082"


def test_clean_id_blank_is_empty():
    assert _clean_id("") == ""
    assert _clean_id(",,") == ""


def test_ddmmyyyy_conversion():
    assert _ddmmyyyy_to_yyyymmdd("05/06/1983") == "19830605"
    assert _ddmmyyyy_to_yyyymmdd("") == ""


def test_surname_strips_title_and_initials():
    assert _surname_from_employee_name("Mr J Baardnes") == "Baardnes"
    assert _surname_from_employee_name("S Anthorn") == "Anthorn"
    assert _surname_from_employee_name("R van Wyk") == "van Wyk"


def test_parse_extracts_id_employee():
    records = parse(SAMPLE_EMPLOYEES.encode("cp1252"))
    emp = records["7"]
    assert emp.surname == "Sample"
    assert emp.first_names == "Jane"
    assert emp.id_number == "8306056177085"
    assert emp.passport_number == ""
    assert emp.date_of_birth == "19830605"
    assert emp.date_engaged == "20230824"
    assert emp.end_date == ""
    assert emp.employee_status == "Normal"
    assert emp.uif_status == "Contributes"


def test_parse_extracts_passport_employee_with_end_date():
    records = parse(SAMPLE_EMPLOYEES.encode("cp1252"))
    emp = records["12"]
    assert emp.surname == "van Wyk"
    assert emp.id_number == ""
    assert emp.passport_number == "BN487879"
    assert emp.date_engaged == "20220515"
    assert emp.end_date == "20241224"
    assert emp.employee_status == "Terminated"
