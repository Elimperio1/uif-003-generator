"""
UI-19 form rows: the standalone UI19 script's rules, applied to parsed data.

Ported from UI19_Automation_7/sage_reader.py (employees_from_ytd_detail and
its name helpers). The eDecs rules in generate_003 / validate do not apply
here: each output follows its own rules
(docs/superpowers/specs/2026-09-14-ui19-pdf-design.md).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import EmployeeRecord, YtdRecord

# The form's own "Reason for non-contribution" table (column J).
NON_CONTRIBUTOR_REASONS = {
    "1": "Temporary employees (less than 24 hours per month)",
    "2": "Learners in terms of the skills development Act",
    "3": "Employees in the National and Provincial spheres of Government",
    "4": "Employees who are repatriated at the end of their contract of service",
    "5": "Employees who earn commission only",
    "6": "No income paid for the payroll period",
    "7": "Employees in receipt of an Old Age Pension from the state",
    "8": "Employees who receive a pension payment from Employer",
    "9": "Above the ceiling",
}
NO_INCOME_REASON = "6"
ID_BOXES = 13

SURNAME_PREFIXES = {
    "van", "de", "der", "von", "du", "le", "la", "af", "het", "ten", "ter",
    "bin", "ibn", "el", "al", "da", "dos", "das", "st", "o",
}
# "mt" is not in the script's list: added so "Mt N Langeni" splits the way the
# eDecs parser already handles it (spec deviation 11).
NAME_TITLES = {"mr", "mrs", "ms", "miss", "dr", "prof", "rev", "adv", "mx", "sir", "dame", "mt"}


@dataclass
class FormRow:
    """One employee row of the UI-19 table."""

    employee_code: str
    surname: str
    initials: str
    id_number: str
    gross: float
    hours_worked: float | None
    commencement_date: str                 # YYYYMMDD or ""
    termination_date: str                  # YYYYMMDD or ""
    uif_contributor: str                   # "YES" / "NO" / ""
    termination_reason_code: str = ""      # column H
    non_contributor_reason_code: str = ""  # column J


def split_full_name(full_name: str) -> tuple[str, str]:
    """'Leethan Van de Rheede' -> ('Van de Rheede', 'L.')."""
    words = full_name.split()
    if not words:
        return "", ""
    if len(words) == 1:
        return words[0], ""
    surname_start = len(words) - 1
    for i in range(1, len(words)):
        if words[i].lower().rstrip(".") in SURNAME_PREFIXES:
            surname_start = i
            break
    surname = " ".join(words[surname_start:])
    initials = "".join(w[0].upper() + "." for w in words[:surname_start] if w)
    return surname, initials


def initials_from_first_names(first_names: str) -> str:
    """'Petrus Johannes' -> 'P.J.'"""
    parts = re.split(r"[\s\-]+", (first_names or "").strip())
    return "".join(p[0].upper() + "." for p in parts if p)


def _format_initials(tokens: list[str]) -> str:
    """['E'] -> 'E.'; ['JP'] -> 'J.P.'"""
    out = []
    for token in tokens:
        token = token.strip(".")
        if len(token) == 1:
            out.append(token.upper() + ".")
        else:
            out.extend(ch.upper() + "." for ch in token)
    return "".join(out)


def split_employee_detail_name(name: str) -> tuple[str, str]:
    """Sage 'Title Initial(s) Surname': 'Ms E Smart' -> ('Smart', 'E.')."""
    words = name.split()
    if not words:
        return "", ""
    idx = 1 if words[0].strip(".").lower() in NAME_TITLES else 0
    initial_tokens = []
    while idx < len(words) - 1 and words[idx].isupper() and len(words[idx].strip(".")) <= 3:
        initial_tokens.append(words[idx])
        idx += 1
    surname = " ".join(words[idx:]) if idx < len(words) else words[-1]
    return surname, _format_initials(initial_tokens)


def _name(ytd: YtdRecord, emp: EmployeeRecord | None) -> tuple[str, str]:
    if emp is not None:
        if emp.employee_name:
            surname, initials = split_employee_detail_name(emp.employee_name)
        else:
            surname, initials = emp.surname, initials_from_first_names(emp.full_names)
        if surname:
            return surname, initials
    return split_full_name(ytd.employee_name)


def _contributor(emp: EmployeeRecord | None, uif_amount: float | None) -> str:
    if emp is not None and emp.uif_status_reported and emp.uif_status:
        status = emp.uif_status.strip().lower()
        if "does not" in status or "exempt" in status or status == "no":
            return "NO"
        if "contribut" in status:
            return "YES"
    if uif_amount is not None:
        return "YES" if uif_amount > 0 else "NO"
    return ""


def _in_period(date_yyyymmdd: str, period_yyyymm: str) -> bool:
    return bool(date_yyyymmdd) and date_yyyymmdd[:6] == period_yyyymm


def form_rows(
    ytd: dict[str, YtdRecord],
    employees: dict[str, EmployeeRecord],
    month: str,
    period_yyyymm: str,
) -> tuple[list[FormRow], list[str]]:
    """Rows for one month's UI-19, in report order, plus the script's warnings."""
    rows: list[FormRow] = []
    notes: list[str] = []
    any_missing_id = any_missing_hours = False
    unmatched = 0

    for code, record in ytd.items():
        emp = employees.get(code)
        surname, initials = _name(record, emp)
        if not surname:
            continue

        start = emp.date_engaged if emp and emp.date_engaged else record.start_date
        end = emp.end_date if emp and emp.end_date else record.end_date
        gross = record.gross(month)
        uif_amount = record.uif_deducted.get(month) if record.uif_deducted else None

        # Sage prints 0.00 in every month after someone leaves, so a zero is not
        # "on payroll": only pay, a UIF deduction, or a start/end this month counts.
        relevant = (
            bool(gross) or bool(uif_amount)
            or _in_period(start, period_yyyymm) or _in_period(end, period_yyyymm)
        )
        if not relevant:
            continue

        label = f"{code} ({surname})"
        id_number = (emp.id_number or emp.passport_number) if emp else ""
        if not id_number:
            any_missing_id = True
        elif len(id_number) > ID_BOXES:
            notes.append(
                f"{label}: ID/passport number {id_number} is longer than the "
                f"form's {ID_BOXES} boxes and will be cut off. Fix that row by "
                f"hand on the PDF."
            )

        contributor = _contributor(emp, uif_amount)
        if not contributor:
            notes.append(
                f"{label}: no UIF deduction line or status found for this "
                f"employee - check the contributor Yes/No column manually."
            )

        hours = emp.average_hours if emp else None
        if hours is None:
            any_missing_hours = True
        if emp is None:
            unmatched += 1

        rows.append(FormRow(
            employee_code=code, surname=surname, initials=initials,
            id_number=id_number, gross=gross, hours_worked=hours,
            commencement_date=start, termination_date=end,
            uif_contributor=contributor,
        ))

    head: list[str] = []
    if any_missing_id:
        head.append(
            "Some employees are missing an ID/passport number - fill it in by "
            "hand (or from your employee master list) before submitting."
        )
    if any_missing_hours and not employees:
        head.append(
            "This report doesn't include hours worked - the 'Total hours "
            "worked' column has been left blank; fill it in if you need it."
        )
    if employees and unmatched:
        head.append(
            f"{unmatched} employee(s) on the payroll this month were not found "
            f"(by employee code) in the Employee Details report - their ID "
            f"number and other details from that report are blank. Check both "
            f"reports are for the same company/period."
        )
    return rows, head + notes


def needs_termination_reason(row: FormRow, period_yyyymm: str) -> bool:
    """Column H applies once the leaving month is within or before the period."""
    return bool(row.termination_date) and row.termination_date[:6] <= period_yyyymm


def default_non_contributor_reason(row: FormRow) -> str | None:
    """Code 6 (no income paid) when there was no pay, else no default."""
    return NO_INCOME_REASON if row.gross == 0 else None


def apply_codes(
    rows: list[FormRow],
    period_yyyymm: str,
    status_overrides: dict[str, str],
    non_contributor_overrides: dict[str, str],
) -> list[FormRow]:
    """Fill H (eDecs code, leading zero dropped) and J from the filer's picks."""
    for row in rows:
        code = row.employee_code
        if needs_termination_reason(row, period_yyyymm) and code in status_overrides:
            row.termination_reason_code = status_overrides[code].lstrip("0")
        if row.uif_contributor == "NO" and code in non_contributor_overrides:
            row.non_contributor_reason_code = non_contributor_overrides[code]
    return rows
