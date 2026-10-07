"""
Employees the payroll data suggests have left, though it doesn't mark them so.

Shared by both output modes. The filer must pick a reason for each one: a
leaving code (which turns the record into a declared leaver, so each mode's own
rules then apply), or a still-employed code such as 01 for an unpaid month.
Nothing is assumed either way.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .generate_003 import termination_date
from .models import TAX_YEAR_MONTHS, TERMINATED_STATUSES, MatchedRecord

# 8280 codes that describe someone still employed. Picking one records why the
# employee looked like a leaver but changes nothing in the output.
STILL_EMPLOYED_CODES = {"01", "09", "10", "17", "19"}


@dataclass
class PossibleLeaver:
    record: MatchedRecord
    why: str          # shown to the filer
    end_date: str     # YYYYMMDD on file, "" when the filer must supply one
    last_paid: str    # month name of the last pay before the gap, or ""


def possible_leavers(
    records: list[MatchedRecord],
    months: list[str],
    periods: dict[str, str],
    already: set[str],
) -> list[PossibleLeaver]:
    """
    Flag, across `months`, anyone not in `already` (leavers each mode lists
    itself) who either has an end date on or before a declared period while
    the payroll still calls them employed, or was paid earlier in the tax year
    but nothing in a declared month.
    """
    # A month nobody was paid in is a month the report doesn't cover yet.
    with_data = [
        m for m in months
        if any(r.ytd is not None and r.ytd.gross(m) > 0 for r in records)
    ]
    found: list[PossibleLeaver] = []
    for record in records:
        ytd = record.ytd
        if ytd is None or record.employee_code in already:
            continue
        if ytd.status in TERMINATED_STATUSES:
            continue
        end = termination_date(record)
        if end:
            if any(end[:6] <= periods[m] for m in months):
                found.append(PossibleLeaver(
                    record,
                    f"End date {end[:4]}-{end[4:6]}-{end[6:]} on file, but the "
                    f"payroll status is still '{ytd.status}'",
                    end, "",
                ))
            continue
        unpaid, last_paid = [], ""
        for month in with_data:
            if ytd.gross(month) > 0:
                continue
            earlier = TAX_YEAR_MONTHS[: TAX_YEAR_MONTHS.index(month)]
            paid = [m for m in earlier if ytd.gross(m) > 0]
            if paid:
                unpaid.append(month)
                last_paid = last_paid or paid[-1]
        if unpaid:
            found.append(PossibleLeaver(
                record,
                f"Paid up to {last_paid}, nothing in {', '.join(unpaid)}",
                "", last_paid,
            ))
    return found


def confirm_leaver(record: MatchedRecord, end_date: str) -> MatchedRecord:
    """A copy of `record` declared as having left, keeping any end date on file."""
    ytd = replace(
        record.ytd,
        status="No longer employed",
        end_date=record.ytd.end_date or termination_date(record) or end_date,
    )
    return replace(record, ytd=ytd)
