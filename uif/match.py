"""
Join the YTD payroll data with the employee master on `employee_code`.

Returns the matched records plus soft-warning messages for any employee that
appears in only one of the two reports.
"""

from __future__ import annotations

from .models import EmployeeRecord, MatchedRecord, YtdRecord


def join(
    ytd: dict[str, YtdRecord],
    employees: dict[str, EmployeeRecord],
) -> tuple[list[MatchedRecord], list[str]]:
    """Join on employee code. Returns (matched_records, warnings)."""
    all_codes = sorted(
        set(ytd) | set(employees),
        key=lambda c: (len(c), c),  # natural-ish order: "2" before "10"
    )

    matched: list[MatchedRecord] = []
    warnings: list[str] = []

    for code in all_codes:
        ytd_record = ytd.get(code)
        emp_record = employees.get(code)
        matched.append(MatchedRecord(code, emp_record, ytd_record))

        if ytd_record is not None and emp_record is None:
            warnings.append(
                f"Employee {code} ({ytd_record.employee_name}) is in the "
                f"Year to Date Detail but not the Employee Details report."
            )
        elif emp_record is not None and ytd_record is None:
            warnings.append(
                f"Employee {code} ({emp_record.first_names} {emp_record.surname}) "
                f"is in the Employee Details but not the Year to Date Detail report."
            )

    return matched, warnings
