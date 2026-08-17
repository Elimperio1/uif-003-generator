"""
Validate joined records for a given month.

Returns (blocking_errors, soft_warnings):
  - blocking errors stop file generation entirely (missing required identity
    fields — SARS uFiling would reject the file);
  - soft warnings are surfaced to the user but do not block the download.
"""

from __future__ import annotations

import calendar

from . import generate_003, sa_id, uif_ref
from .models import (
    CONFIRMED_FULL_REMUNERABLE,
    DEFAULT_NON_CONTRIBUTION_CODE,
    NON_CONTRIBUTION_CODES,
    REMUNERABLE_PCT,
    Company,
    MatchedRecord,
)


def _period_last_day(period_yyyymm: str) -> str:
    """Last calendar day of a YYYYMM period, as YYYYMMDD."""
    year, month = int(period_yyyymm[:4]), int(period_yyyymm[4:6])
    return f"{year}{month:02d}{calendar.monthrange(year, month)[1]:02d}"


def _age_years(dob_yyyymmdd: str, on_yyyymmdd: str) -> int | None:
    """Whole years old on the reference date, or None if the DOB is unparseable."""
    try:
        by, bm, bd = int(dob_yyyymmdd[:4]), int(dob_yyyymmdd[4:6]), int(dob_yyyymmdd[6:8])
        ry, rm, rd = int(on_yyyymmdd[:4]), int(on_yyyymmdd[4:6]), int(on_yyyymmdd[6:8])
    except ValueError:
        return None
    if not (1 <= bm <= 12 and 1 <= bd <= 31):
        return None
    return ry - by - ((rm, rd) < (bm, bd))


def validate_company(company: Company) -> list[str]:
    """
    Soft warnings about the filer configuration itself.

    An invalid 8020 rejects the whole file, so it is worth flagging before
    anything is generated — but the check-digit routine in the spec's own
    Appendix A cannot verify every real reference, so this never blocks.
    """
    warnings = list(uif_ref.describe(company.uif_ref))

    paye = company.paye_ref.strip()
    if paye and not (paye.isdigit() and len(paye) == 10 and paye.startswith("7")):
        # Spec §8, rule 8120: "This number starts with a '7' and must be a
        # valid reference number as supplied by SARS." Invalid is a warning,
        # not a rejection.
        warnings.append(
            f"PAYE reference '{paye}' is not the 10 digits starting with 7 "
            f"that field 8120 expects — SARS will warn on it."
        )

    # Spec §7 declared lengths: 8060/8160 email 50, 8040 name 30, 8050 phone 16.
    # `_field` truncates on output; warn so a cut email address, in particular,
    # is not a silent surprise.
    for value, length, label in (
        (company.contact_email_header, 50, "Contact email (header, field 8060)"),
        (company.contact_email_footer, 50, "Contact email (footer, field 8160)"),
        (company.contact_name, 30, "Contact name (field 8040)"),
        (company.contact_phone, 16, "Contact phone (field 8050)"),
    ):
        if len(value) > length:
            warnings.append(
                f"{label} is {len(value)} characters; it will be cut to the "
                f"{length} the spec allows."
            )
    return warnings


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
    period_yyyymm: str | None = None,
) -> tuple[list[str], list[str]]:
    """
    Validate the records that would appear in `month`'s declaration file.

    `period_yyyymm` (field 8070, e.g. "202502") enables the §9 date checks that
    need to know the declared period — termination before start, a start date in
    the future, and an employee younger than 15. It defaults to None so existing
    callers keep working; the date checks are simply skipped when it is absent.
    """
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
            # Spec §8/§9: a record is rejected only when none of 8200, 8210 or
            # 8220 is present, and 8220 takes "the personnel, clock card or
            # payroll number". The file is valid; the employee's details are
            # held in a secondary database until an ID is supplied.
            soft.append(
                f"{label}: has neither an ID number nor a passport number — "
                f"declared on payroll number {record.employee_code} in field "
                f"8220. The record is accepted, but the employee cannot claim "
                f"benefits until a valid ID number is supplied."
            )

        # Spec rule 8200 + Appendix B: an invalid but present ID is a warning,
        # not a rejection — SARS holds the record in a secondary database and the
        # employee cannot claim until it is corrected. One warning per problem,
        # each with the consequence spelled out.
        if emp.id_number:
            for reason in sa_id.problems(emp.id_number, emp.date_of_birth):
                fix = ""
                if "scientific-notation" in reason:
                    fix = (
                        " Fix the Employee Details file (format the ID column as "
                        "Number, 0 decimals) and re-upload."
                    )
                soft.append(
                    f"{label}: {reason}. SARS accepts the record but flags the "
                    f"ID invalid, holds it in a secondary database, and the "
                    f"employee cannot claim until it is corrected.{fix}"
                )

        # Spec §5 encloses alphanumeric fields in double quotes but defines no
        # escaping, so a comma inside a quoted value is ambiguous. It is written
        # unchanged; the filer is warned to confirm SARS accepts it.
        for value, field_name in (
            (emp.surname, "surname"),
            (emp.first_names, "first names"),
            (emp.passport_number, "passport number"),
        ):
            if value and "," in value:
                soft.append(
                    f"{label}: the {field_name} contains a comma; it will be "
                    f"written inside quotes, but the spec (§5) defines no "
                    f"escaping — verify SARS accepts it, or remove the comma in "
                    f"the source file."
                )

        # Spec §9 date warnings — only meaningful once the declared period is
        # known (field 8070).
        if period_yyyymm is not None:
            last_day = _period_last_day(period_yyyymm)
            end_date = generate_003.termination_date(record)
            start_date = emp.date_engaged

            if (
                generate_003.is_terminated_in_period(record, period_yyyymm)
                and end_date
                and start_date
                and end_date < start_date
            ):
                soft.append(
                    f"{label}: employment end date {end_date} (field 8270) is "
                    f"before the start date {start_date} (field 8260) — spec §9. "
                    f"SARS will warn on it."
                )

            if start_date and start_date > last_day:
                soft.append(
                    f"{label}: employment start date {start_date} (field 8260) "
                    f"is after the end of the declared period {period_yyyymm} — "
                    f"spec §9 flags a start date in the future. SARS will warn."
                )

            age = _age_years(emp.date_of_birth, last_day) if emp.date_of_birth else None
            if age is not None and age < 15:
                soft.append(
                    f"{label}: date of birth {emp.date_of_birth} makes the "
                    f"employee younger than 15 on the last day of the declared "
                    f"period ({last_day}) — spec §9 (8250). SARS will warn."
                )

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
                f"UIF-remunerable — included with zero UIF and reason code "
                f"8290 = {DEFAULT_NON_CONTRIBUTION_CODE} "
                f"({NON_CONTRIBUTION_CODES[DEFAULT_NON_CONTRIBUTION_CODE]}). "
                f"Verify that reason fits."
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
