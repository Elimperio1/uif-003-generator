"""
Validate joined records for a given month.

Returns (blocking_errors, soft_warnings):
  - blocking errors stop file generation entirely (missing required identity
    fields — SARS uFiling would reject the file);
  - soft warnings are surfaced to the user but do not block the download.

Also exposes raw-cell corruption detectors that run during parsing on the
literal CSV cell strings, before any numeric conversion.
"""

from __future__ import annotations

from typing import NamedTuple

from .models import CONFIRMED_FULL_REMUNERABLE, REMUNERABLE_PCT, MatchedRecord


class MonetaryCorruption(NamedTuple):
    """One corrupted monetary cell, captured at parse time."""

    employee_code: str
    employee_name: str
    month: str
    field_name: str
    raw_value: str


def looks_like_missing_decimal(raw_value) -> bool:
    """
    Detect monetary values that have lost their decimal places.

    The Sage CSV format always emits monetary values with 2 decimal places
    (e.g. "5000.00", "103.45"). A pure-integer string with no decimal
    point is almost certainly a value that was originally "103,45" (South
    African comma decimal) and got corrupted by Excel handling the file
    under a US/UK locale where comma is a thousands separator. The
    resulting value is 100x too large.

    IMPORTANT: this check MUST be called on the raw string read from the
    CSV cell BEFORE any numeric conversion. Once the value has been
    converted to Decimal or float, the corruption signature is lost.

    Returns:
        True if the raw value looks corrupted, False otherwise. Zero,
        blank, and None all return False (handled by other validation).
    """
    if raw_value is None:
        return False
    s = str(raw_value).strip()
    if not s or s == "0":
        return False
    if s.startswith("-"):
        s = s[1:]
    return s.isdigit()


def _label(record: MatchedRecord) -> str:
    if record.employee is not None:
        name = f"{record.employee.first_names} {record.employee.surname}".strip()
    elif record.ytd is not None:
        name = record.ytd.employee_name
    else:
        name = ""
    return f"Employee {record.employee_code}" + (f" ({name})" if name else "")


def validate(
    records: list[MatchedRecord],
    month: str,
) -> tuple[list[str], list[str]]:
    """Validate the records that would appear in `month`'s declaration file."""
    blocking: list[str] = []
    soft: list[str] = []
    unknown_earnings: set[str] = set()

    for record in records:
        if record.ytd is None or record.ytd.gross(month) <= 0:
            continue  # not included in this month's file

        label = _label(record)
        emp = record.employee

        if emp is None:
            blocking.append(
                f"{label}: appears in the Year to Date Detail but has no "
                f"Employee Details record — identity fields (ID, date of birth, "
                f"employment dates) are unavailable."
            )
            continue

        if not emp.id_number and not emp.passport_number:
            blocking.append(f"{label}: has neither an ID number nor a passport number.")
        if not emp.date_of_birth:
            blocking.append(f"{label}: has no date of birth.")
        if not emp.date_engaged:
            blocking.append(f"{label}: has no employment start date.")
        if not emp.surname:
            blocking.append(f"{label}: has no surname.")
        if not emp.first_names:
            blocking.append(f"{label}: has no first name.")

        if emp.uif_status and emp.uif_status.strip().lower() != "contributes":
            soft.append(
                f"{label}: UIF status is '{emp.uif_status}', not 'Contributes' "
                f"— included anyway; verify this is correct."
            )

        if record.ytd.gross(month) > 0 and record.ytd.remunerable(month) == 0:
            soft.append(
                f"{label}: has gross earnings for {month} but R0 is "
                f"UIF-remunerable — included with zero UIF."
            )

        for earning_name in record.ytd.earnings.get(month, {}):
            if (
                earning_name not in REMUNERABLE_PCT
                and earning_name not in CONFIRMED_FULL_REMUNERABLE
            ):
                unknown_earnings.add(earning_name)

    for name in sorted(unknown_earnings):
        soft.append(
            f"Earning type '{name}' is not in the UIF-remunerability map — "
            f"assumed 100% UIF-remunerable. Verify this is correct."
        )

    return blocking, soft
