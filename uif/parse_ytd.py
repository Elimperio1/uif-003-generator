"""
Parser for the Sage "Year to Date Detail" CSV.

The report is a block-structured layout, one block per employee:

    Employee code:,32,,Employee name:,,Sibonile Anthorn Anthorn,...
    ,,,,,,Status: Employed; From: 2023/08/24; ...
    Earnings,,...
    Basic salary,,6 557.76,,7 057.76,,,...
    ... more earning line items ...
    TOTAL,,...
    Deductions,,...
    ...

A header row near the top maps month names to (irregular) column indices.
We only need the Earnings section: every line item, per month, so that both
gross and UIF-remunerable earnings can be derived later.
"""

from __future__ import annotations

import csv
import io
import re

from .models import TAX_YEAR_MONTHS, YtdRecord
from .parse_employees import parse_employee_code
from .validate import MonetaryCorruption, looks_like_missing_decimal

_SECTION_HEADERS = {
    "Earnings", "Deductions", "Company Contributions",
    "Fringe Benefits", "Tax Deductible Deductions", "Other Totals",
}


def _decode(file_bytes: bytes) -> str:
    """Sage exports are usually cp1252 (non-breaking-space thousands separator)."""
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return file_bytes.decode("latin-1", errors="replace")


def _num(cell: str) -> float:
    """Parse a Sage numeric cell ('6 187.50', '0', '', '-85.15') to float."""
    cleaned = cell.replace("\xa0", "").replace(" ", "").replace(",", "").strip()
    if not cleaned:
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _slash_date_to_yyyymmdd(date_str: str) -> str:
    """'2023/12/31' -> '20231231'. Returns '' if not parseable."""
    match = re.search(r"(\d{4})/(\d{2})/(\d{2})", date_str)
    return f"{match.group(1)}{match.group(2)}{match.group(3)}" if match else ""


def tax_year_end_year(file_bytes: bytes) -> int:
    """
    Read the tax-year-end year from the 'Printed for period ending' line.

    e.g. 'Printed for period ending 2025/02/28' -> 2025.
    """
    text = _decode(file_bytes)
    match = re.search(r"period ending\s+(\d{4})/\d{2}/\d{2}", text)
    if not match:
        raise ValueError(
            "Could not find the 'Printed for period ending' line in the YTD CSV."
        )
    return int(match.group(1))


def _find_month_columns(rows: list[list[str]]) -> dict[str, int]:
    """Locate the month-header row and map each month name to its column index."""
    for row in rows:
        cells = [c.strip() for c in row]
        if "March" in cells and "February" in cells:
            return {m: cells.index(m) for m in TAX_YEAR_MONTHS if m in cells}
    raise ValueError("Could not find the month-header row in the YTD CSV.")


def _parse_status(text: str) -> tuple[str, str]:
    """Extract (status, end_date_yyyymmdd) from a 'Status: ...' cell."""
    status_match = re.search(r"Status:\s*([^;]+)", text)
    status = status_match.group(1).strip() if status_match else ""
    to_match = re.search(r"To:\s*(\d{4}/\d{2}/\d{2})", text)
    end_date = _slash_date_to_yyyymmdd(to_match.group(1)) if to_match else ""
    return status, end_date


def parse(
    file_bytes: bytes,
) -> tuple[dict[str, YtdRecord], list[MonetaryCorruption]]:
    """
    Parse the YTD CSV into ``({employee_code: YtdRecord}, corruption_errors)``.

    Every monetary cell read during parsing is also checked, in its raw
    string form, against ``looks_like_missing_decimal``. Any hit is
    captured as a ``MonetaryCorruption`` entry for the UI to surface; the
    parser still stores the (potentially-wrong) numeric value so the user
    can see what would have been generated, but generation must be
    blocked when this list is non-empty for any selected month.
    """
    text = _decode(file_bytes)
    rows = list(csv.reader(io.StringIO(text)))
    month_cols = _find_month_columns(rows)

    records: dict[str, YtdRecord] = {}
    corruption: list[MonetaryCorruption] = []
    current: YtdRecord | None = None
    section: str = ""
    expecting_status = False

    def _check_monetary_row(field_name: str) -> None:
        """Scan every month cell on `row` and record any missing-decimal hits."""
        for month, col in month_cols.items():
            raw = row[col] if col < len(row) else ""
            if looks_like_missing_decimal(raw):
                corruption.append(
                    MonetaryCorruption(
                        employee_code=current.employee_code,
                        employee_name=current.employee_name,
                        month=month,
                        field_name=field_name,
                        raw_value=str(raw).strip(),
                    )
                )

    for row in rows:
        if not row:
            continue
        first = row[0].strip()

        if first == "REPORT SUMMARY":
            break

        if first == "Employee code:":
            code = parse_employee_code(row[1] if len(row) > 1 else "")
            name = row[5].strip() if len(row) > 5 else ""
            current = YtdRecord(
                employee_code=code,
                employee_name=name,
                status="",
                earnings={m: {} for m in TAX_YEAR_MONTHS},
            )
            records[code] = current
            section = ""
            expecting_status = True
            continue

        if current is None:
            continue

        if expecting_status:
            expecting_status = False
            joined = " ".join(row)
            if "Status:" in joined:
                current.status, current.end_date = _parse_status(joined)
                continue
            # No status row present; fall through to normal handling.

        if first in _SECTION_HEADERS:
            section = first
            continue

        if section == "Earnings" and first:
            if first == "TOTAL":
                # The Earnings TOTAL row. Don't store it (gross is derived
                # from the line items) but still check every cell for
                # missing-decimal corruption.
                _check_monetary_row("gross earnings")
            else:
                _check_monetary_row(first)
                for month, col in month_cols.items():
                    amount = _num(row[col]) if col < len(row) else 0.0
                    if amount:
                        current.earnings[month][first] = (
                            current.earnings[month].get(first, 0.0) + amount
                        )
        elif section == "Deductions" and first == "Unemployment insurance fund":
            _check_monetary_row("UIF deduction")
        elif (
            section == "Company Contributions"
            and first == "Unemployment insurance fund"
        ):
            _check_monetary_row("UIF company contribution")

    return records, corruption
