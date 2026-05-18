"""
Validate joined records for a given month.

Returns (blocking_errors, soft_warnings):
  - blocking errors stop file generation entirely (missing required identity
    fields — SARS uFiling would reject the file);
  - soft warnings are surfaced to the user but do not block the download.
"""

from __future__ import annotations

from .models import CONFIRMED_FULL_REMUNERABLE, REMUNERABLE_PCT, MatchedRecord


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
