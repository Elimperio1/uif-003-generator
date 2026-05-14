"""
Parser for the Sage "Employee Details" CSV.

The report is label/value rows, multiple blocks per employee. Crucially the
value sits in a *different column depending on the row* (col 1, 2, or 11), so
values are located relative to their label, bounded by the next known label on
the same row.

Key fields used by the .003:
    Employee code, Employee name (initial + surname), Full names (first names),
    ID number, Passport number, Date of birth, Date Engaged, End date,
    Employee status, UIF status.
"""

from __future__ import annotations

import csv
import io
import re

from .models import EmployeeRecord

# Every label that can appear in column position — used to bound value scans.
KNOWN_LABELS = {
    "Personal Details", "Employee code", "Employee name", "Full names",
    "Known as", "ID number", "Date of birth", "Age", "Passport number",
    "Passport country", "Classification Codes", "Department Code",
    "Department Description", "Pay Point Code", "Pay Point Description",
    "Contact Details", "Residential address", "Postal address", "Work address",
    "Email address", "Home phone number", "Work phone number",
    "Cell phone number", "Fax number", "Payment Details", "Pay method",
    "Branch number", "Account type", "Account number", "Account holder name",
    "Relationship", "Bank name", "Branch name", "Employment Details",
    "Pay cycle", "Occupation", "Date Engaged", "End date", "Tax status",
    "Employee status", "Tax number", "Directive percentage", "Directive number",
    "UIF status", "Exclude for SDL", "Hours and Rates", "Working hours per day",
    "Annual salary/wage", "Working days per week", "Fixed salary/wage",
    "Average working hours per period", "Rate per day",
    "Average working days per period", "Rate per hour", "Benefit Details",
}

_TITLES = {"mr", "mrs", "ms", "miss", "dr", "prof"}


def _decode(file_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return file_bytes.decode("latin-1", errors="replace")


def _value_for(row: list[str], label: str) -> str:
    """First non-empty cell after `label`, bounded by the next known label."""
    stripped = [c.strip() for c in row]
    try:
        start = stripped.index(label)
    except ValueError:
        return ""
    # Find the next known label after `start`, which bounds this value.
    end = len(stripped)
    for i in range(start + 1, len(stripped)):
        if stripped[i] in KNOWN_LABELS:
            end = i
            break
    for i in range(start + 1, end):
        if stripped[i]:
            return stripped[i]
    return ""


def _strip_decimal_suffix(value: str) -> str:
    """'32.00' -> '32', '8306056177085.00' -> '8306056177085'."""
    return value.split(".")[0].strip()


def _clean_id(value: str) -> str:
    """Digits only, left-padded to 13. Excel can drop the leading zero."""
    digits = re.sub(r"\D", "", _strip_decimal_suffix(value))
    if not digits:
        return ""
    return digits.zfill(13) if len(digits) <= 13 else digits


def _ddmmyyyy_to_yyyymmdd(value: str) -> str:
    """'05/06/1983' -> '19830605'. Returns '' if not parseable."""
    match = re.search(r"(\d{2})/(\d{2})/(\d{4})", value)
    return f"{match.group(3)}{match.group(2)}{match.group(1)}" if match else ""


def _surname_from_employee_name(employee_name: str) -> str:
    """'Mr J Baardnes' -> 'Baardnes', 'R van Wyk' -> 'van Wyk'."""
    tokens = employee_name.split()
    while tokens:
        head = tokens[0]
        if head.lower().rstrip(".") in _TITLES or len(head.rstrip(".")) == 1:
            tokens.pop(0)
        else:
            break
    return " ".join(tokens).strip()


def parse(file_bytes: bytes) -> dict[str, EmployeeRecord]:
    """Parse the Employee Details CSV into {employee_code: EmployeeRecord}."""
    text = _decode(file_bytes)
    rows = list(csv.reader(io.StringIO(text)))

    records: dict[str, EmployeeRecord] = {}
    block: list[list[str]] = []

    def flush(block_rows: list[list[str]]) -> None:
        if not block_rows:
            return
        fields: dict[str, str] = {}
        for label in (
            "Employee code", "Employee name", "Full names", "ID number",
            "Passport number", "Date of birth", "Date Engaged", "End date",
            "Employee status", "UIF status",
        ):
            for r in block_rows:
                value = _value_for(r, label)
                if value:
                    fields[label] = value
                    break
            fields.setdefault(label, "")

        code = _strip_decimal_suffix(fields["Employee code"])
        if not code:
            return
        records[code] = EmployeeRecord(
            employee_code=code,
            surname=_surname_from_employee_name(fields["Employee name"]),
            first_names=fields["Full names"].strip(),
            id_number=_clean_id(fields["ID number"]),
            passport_number=fields["Passport number"].strip(),
            date_of_birth=_ddmmyyyy_to_yyyymmdd(fields["Date of birth"]),
            date_engaged=_ddmmyyyy_to_yyyymmdd(fields["Date Engaged"]),
            end_date=_ddmmyyyy_to_yyyymmdd(fields["End date"]),
            employee_status=fields["Employee status"].strip(),
            uif_status=fields["UIF status"].strip(),
        )

    for row in rows:
        first = row[0].strip() if row else ""
        if first == "Employee code":
            flush(block)
            block = [row]
        elif block:
            block.append(row)
    flush(block)

    return records
