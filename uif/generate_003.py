"""
Build a SARS UIF declaration file from joined records for a single month.

Format and rules are verified against the real Sage samples 20440843.003
(period 202402) and 20440843.004 (period 202502). See FORMAT.md.
"""

from __future__ import annotations

from .models import (
    DEFAULT_STATUS_CODE,
    STATUS_CODE,
    TERMINATED_STATUSES,
    UIF_RATE_PER_SIDE,
    UIF_REMUNERATION_CAP,
    Company,
    MatchedRecord,
)


def _fmt(value: float) -> str:
    """Two decimals, but a trailing '.00' is dropped ('11550', '6232.80')."""
    text = f"{value:.2f}"
    return text[:-3] if text.endswith(".00") else text


def _q(value: str) -> str:
    return f'"{value}"'


def _code_sort_key(record: MatchedRecord):
    code = record.employee_code
    return (0, int(code)) if code.isdigit() else (1, code)


def employee_figures(record: MatchedRecord, month: str) -> tuple[float, float, float]:
    """Return (gross 8300, remuneration 8310, uif total 8320) for one month."""
    gross = record.ytd.gross(month)
    remuneration = min(record.ytd.remunerable(month), UIF_REMUNERATION_CAP)
    employee_side = round(remuneration * UIF_RATE_PER_SIDE, 2)
    uif_total = round(employee_side * 2, 2)
    return gross, remuneration, uif_total


def included_for_month(records: list[MatchedRecord], month: str) -> list[MatchedRecord]:
    """Employees with gross earnings > 0 in `month`, in employee-code order."""
    included = [
        r for r in records
        if r.ytd is not None and r.ytd.gross(month) > 0
    ]
    included.sort(key=_code_sort_key)
    return included


def build(
    records: list[MatchedRecord],
    month: str,
    period_yyyymm: str,
    company: Company,
) -> bytes:
    """Build the declaration file bytes for `month` (e.g. 'February')."""
    included = included_for_month(records, month)
    lines: list[str] = []

    lines.append(",".join([
        "8000", _q("UICR"),
        "8010", _q("U1"),
        "8015", _q("E03"),
        "8020", _q(company.uif_ref),
        "8030", _q(company.submission_mode),
        "8040", _q(company.contact_name),
        "8050", _q(company.contact_phone),
        "8060", _q(company.contact_email_header),
        "8070", period_yyyymm,
    ]))

    sum_gross = sum_remuneration = sum_uif = 0.0
    for record in included:
        emp = record.employee
        gross, remuneration, uif_total = employee_figures(record, month)
        sum_gross += gross
        sum_remuneration += remuneration
        sum_uif += uif_total

        fields: list[str] = ["8001", _q("UIWK"), "8110", _q(company.uif_ref)]

        if emp is not None and emp.id_number:
            fields += ["8200", emp.id_number]
        elif emp is not None and emp.passport_number:
            fields += ["8210", _q(emp.passport_number)]

        fields += ["8230", _q(emp.surname if emp else "")]
        fields += ["8240", _q((emp.first_names if emp else "")[:12])]
        fields += ["8250", emp.date_of_birth if emp else ""]
        fields += ["8260", emp.date_engaged if emp else ""]

        status = record.ytd.status
        if status in TERMINATED_STATUSES and record.ytd.end_date:
            fields += ["8270", record.ytd.end_date]
        fields += ["8280", STATUS_CODE.get(status, DEFAULT_STATUS_CODE)]

        fields += [
            "8300", _fmt(gross),
            "8310", _fmt(remuneration),
            "8320", _fmt(uif_total),
        ]
        lines.append(",".join(fields))

    lines.append(",".join([
        "8002", _q("UIEM"),
        "8115", _q(company.uif_ref),
        "8120", company.paye_ref,
        "8130", _fmt(round(sum_gross, 2)),
        "8135", _fmt(round(sum_remuneration, 2)),
        "8140", _fmt(round(sum_uif, 2)),
        "8150", str(len(included)),
        "8160", _q(company.contact_email_footer),
    ]))

    return ("\r\n".join(lines) + "\r\n").encode("latin-1", errors="replace")
