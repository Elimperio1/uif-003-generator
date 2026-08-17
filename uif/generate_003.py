"""
Build a SARS UIF declaration file from joined records for a single month.

Format and rules are verified against the real Sage samples 20440843.003
(period 202402) and 20440843.004 (period 202502), and against
``ELECTRONIC DECLARATION SPECIFICATIONS - E03 (1).pdf``. See FORMAT.md.
"""

from __future__ import annotations

import unicodedata
from decimal import ROUND_HALF_UP, Decimal

from . import sa_id, uif_ref
from .models import (
    DEFAULT_NON_CONTRIBUTION_CODE,
    DEFAULT_STATUS_CODE,
    FIELD_LENGTHS,
    STATUS_CODE,
    STATUSES_WITHOUT_END_DATE,
    TERMINATED_STATUSES,
    UIF_REMUNERATION_CAP,
    Company,
    MatchedRecord,
)

# Characters that NFKD cannot decompose into an ASCII base plus combining
# marks. Spec §5 requires ASCII, and a mangled surname is worse than a
# transliterated one.
_ASCII_FALLBACKS = str.maketrans({
    "ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE",
    "ß": "ss", "đ": "d", "Đ": "D", "ł": "l", "Ł": "L", "ð": "d", "Ð": "D",
    "þ": "th", "Þ": "TH", "’": "'", "‘": "'", "“": "'", "”": "'",
    "–": "-", "—": "-",
})


def to_ascii(text: str) -> str:
    """
    Fold text to ASCII, as spec §5 requires ("must be submitted in ASCII").

    Accented letters are transliterated rather than replaced, so "Böhme"
    becomes "Bohme" and not "B?hme".
    """
    folded = text.translate(_ASCII_FALLBACKS)
    decomposed = unicodedata.normalize("NFKD", folded)
    without_marks = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return without_marks.encode("ascii", errors="replace").decode("ascii")


def compute_uif_total(remunerable) -> Decimal:
    """
    Compute the combined UIF contribution (employee 1% + employer 1%) on
    a remunerable amount, matching Sage: round each half independently
    using ROUND_HALF_UP, then sum.

    Args:
        remunerable: The remunerable amount (field 8310) — already capped
            at R17,712.00 if applicable. Accepts Decimal, float, int, or
            numeric string.

    Returns:
        Decimal with exactly 2 decimal places, for field 8320.
    """
    rem = Decimal(str(remunerable))
    one_percent = (rem * Decimal("0.01")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return one_percent + one_percent


def build_filename(ref: str, sequence: int) -> str:
    """
    Build the output filename for a single UIF declaration file.

    Spec §12: the name is ``uuuuuuuu.nnn``, where ``uuuuuuuu`` is "the last 8
    digits of the creator's UIF Reference number (field 8020)... Only numeric
    digits are allowed and the slash between the last two digits must be
    excluded", and ``nnn`` is a 3-digit file number.

    Args:
        ref: The UIF reference number in any form the user might type it —
            ``"020440843"``, ``"2044084/3"``, ``"20440843"``. It is normalised
            to nine digits before the last eight are taken.
        sequence: The file number. Spec §12 wants this incremented for every
            submission under the same reference, because "if a file is sent
            more than once with the same file name, the last file received
            will be used, and it will overwrite all previously sent files
            with the same file name."

    Returns:
        Filename string, e.g. "20440843.001".

    Examples:
        >>> build_filename("020440843", 1)
        '20440843.001'
        >>> build_filename("1234567/8", 3)     # the spec's own example
        '12345678.003'
        >>> build_filename("000123456", 5)
        '00123456.005'
    """
    digits = uif_ref.normalise(ref)
    return f"{digits[-8:]}.{sequence:03d}"


def _fmt(value) -> str:
    """Two decimals, but a trailing '.00' is dropped ('11550', '6232.80')."""
    text = f"{value:.2f}"
    return text[:-3] if text.endswith(".00") else text


def _sanitise(value: str) -> str:
    """
    Fold to ASCII (spec §5), then make the value safe inside a double-quoted
    field.

    The field delimiter is itself a double quote and the spec defines no
    escaping, so any straight ``"`` left after transliteration becomes an
    apostrophe. Every control character — CR, LF, TAB, and anything below 0x20
    or the 0x7f DEL — collapses to a single space so it cannot split the record
    across lines. Callers apply the length cut *after* this, because folding can
    change length and a control char must not be sliced mid-replacement.
    """
    folded = to_ascii(value).replace('"', "'")
    return "".join(" " if (char < " " or char == "\x7f") else char for char in folded)


def _q(value: str) -> str:
    return f'"{_sanitise(value)}"'


def _field(code: str, value: str) -> str:
    """Quote a value, folded/sanitised to ASCII and cut to the spec's length."""
    return f'"{_sanitise(value)[: FIELD_LENGTHS[code]]}"'


def _code_sort_key(record: MatchedRecord):
    code = record.employee_code
    return (0, int(code)) if code.isdigit() else (1, code)


def employee_figures(record: MatchedRecord, month: str) -> tuple[float, float, Decimal]:
    """Return (gross 8300, remuneration 8310, uif total 8320) for one month."""
    gross = record.ytd.gross(month)
    remuneration = min(record.ytd.remunerable(month), UIF_REMUNERATION_CAP)
    uif_total = compute_uif_total(f"{remuneration:.2f}")
    return gross, remuneration, uif_total


def included_for_month(records: list[MatchedRecord], month: str) -> list[MatchedRecord]:
    """Employees with gross earnings > 0 in `month`, in employee-code order."""
    included = [
        r for r in records
        if r.ytd is not None and r.ytd.gross(month) > 0
    ]
    included.sort(key=_code_sort_key)
    return included


def is_terminated_in_period(record: MatchedRecord, period_yyyymm: str) -> bool:
    """
    Whether this month's record should carry a termination status.

    Termination is per-period: an employee who leaves in a later month was
    still active in this one. Only report the end date and a terminated status
    once the leaving month is within or before the declared period.
    """
    if record.ytd is None:
        return False
    end_date = termination_date(record)
    return bool(
        record.ytd.status in TERMINATED_STATUSES
        and end_date
        and end_date[:6] <= period_yyyymm
    )


def termination_date(record: MatchedRecord) -> str:
    """The 8270 date, preferring the YTD value over the employee record."""
    if record.ytd is None:
        return record.employee.end_date if record.employee else ""
    return record.ytd.end_date or (
        record.employee.end_date if record.employee else ""
    )


def default_status_code(record: MatchedRecord) -> str:
    """The 8280 code implied by the payroll export, before any override."""
    if record.ytd is None:
        return DEFAULT_STATUS_CODE
    return STATUS_CODE.get(record.ytd.status, DEFAULT_STATUS_CODE)


def terminations_for_months(
    records: list[MatchedRecord],
    months: list[str],
    periods: dict[str, str],
) -> list[MatchedRecord]:
    """
    Every employee who is declared as terminated in at least one of `months`.

    These are the records whose 8280 code the filer may need to override —
    the payroll export's status text cannot distinguish a resignation from a
    retrenchment, a dismissal or a death.
    """
    seen: set[str] = set()
    result: list[MatchedRecord] = []
    for month in months:
        for record in included_for_month(records, month):
            if record.employee_code in seen:
                continue
            if is_terminated_in_period(record, periods[month]):
                seen.add(record.employee_code)
                result.append(record)
    result.sort(key=_code_sort_key)
    return result


def build(
    records: list[MatchedRecord],
    month: str,
    period_yyyymm: str,
    company: Company,
    status_overrides: dict[str, str] | None = None,
) -> bytes:
    """
    Build the declaration file bytes for `month` (e.g. 'February').

    Args:
        records: All joined employee records.
        month: Tax-year month name to declare.
        period_yyyymm: Field 8070 for this file, e.g. "202502".
        company: Filer configuration.
        status_overrides: Employee code -> field 8280 code, replacing the
            code inferred from the payroll status text.
    """
    overrides = status_overrides or {}
    included = included_for_month(records, month)
    ref = uif_ref.normalise(company.uif_ref)
    lines: list[str] = []

    lines.append(",".join([
        "8000", _q("UICR"),
        "8010", _q("U1"),
        "8015", _q("E03"),
        "8020", _q(ref),
        "8030", _q(company.submission_mode),
        "8040", _field("8040", company.contact_name),
        "8050", _field("8050", company.contact_phone),
        "8060", _field("8060", company.contact_email_header),
        "8070", period_yyyymm,
    ]))

    sum_gross = sum_remuneration = 0.0
    sum_uif: Decimal = Decimal("0.00")
    for record in included:
        emp = record.employee
        gross, remuneration, uif_total = employee_figures(record, month)
        sum_gross += gross
        sum_remuneration += remuneration
        sum_uif += uif_total

        fields: list[str] = ["8001", _q("UIWK"), "8110", _q(ref)]

        # Spec §8: a record is rejected only when none of 8200, 8210 or 8220
        # is present. 8220 is "the personnel, clock card or payroll number",
        # which the employee code always supplies.
        if emp is not None and emp.id_number:
            fields += ["8200", emp.id_number]
            # Spec rule 8220: "This field is mandatory if fields 8200 or 8210
            # are invalid or not present." When the ID fails validation the
            # record is still accepted (as a warning), but 8220 gives the Fund a
            # payroll number to track the contribution against while the ID sits
            # in the secondary database. Order: 8200, then 8220, then 8230.
            if sa_id.problems(emp.id_number, emp.date_of_birth):
                fields += ["8220", _field("8220", record.employee_code)]
        elif emp is not None and emp.passport_number:
            fields += ["8210", _field("8210", emp.passport_number)]
        else:
            fields += ["8220", _field("8220", record.employee_code)]

        fields += ["8230", _field("8230", emp.surname if emp else "")]
        fields += ["8240", _field("8240", emp.first_names if emp else "")]
        fields += ["8250", emp.date_of_birth if emp else ""]
        fields += ["8260", emp.date_engaged if emp else ""]

        if is_terminated_in_period(record, period_yyyymm):
            status_code = overrides.get(
                record.employee_code, default_status_code(record)
            )
            # Spec §9 warns when 8270 is present alongside status 01, 09 or 10
            # — those describe someone still employed.
            if status_code not in STATUSES_WITHOUT_END_DATE:
                fields += ["8270", termination_date(record)]
            fields += ["8280", status_code]
        else:
            fields += ["8280", DEFAULT_STATUS_CODE]

        # Spec §8: "The Reason code for non-contribution is a required field
        # if the UIF contribution amount is zero." Omitting it draws warnings
        # on 8290, 8300, 8310 and 8320 at once.
        if uif_total == 0:
            fields += ["8290", DEFAULT_NON_CONTRIBUTION_CODE]

        fields += [
            "8300", _fmt(gross),
            "8310", _fmt(remuneration),
            "8320", _fmt(uif_total),
        ]
        lines.append(",".join(fields))

    lines.append(",".join([
        "8002", _q("UIEM"),
        "8115", _q(ref),
        "8120", company.paye_ref,
        "8130", _fmt(round(sum_gross, 2)),
        "8135", _fmt(round(sum_remuneration, 2)),
        "8140", _fmt(sum_uif),
        "8150", str(len(included)),
        "8160", _field("8160", company.contact_email_footer),
    ]))

    return ("\r\n".join(lines) + "\r\n").encode("ascii", errors="replace")
