"""In-memory builders for synthetic Sage report PDFs (no PII).

Each page is drawn as plain text lines so pdfplumber's extract_text returns
them the way it reads the real Sage exports: one report line per text line.
"""

from __future__ import annotations

import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

MONTHS_LINE = (
    "March April May June July August September October November December "
    "January February Total"
)
# Sage stamps the payroll period end here, not the print date, so a report run
# part-way through a tax year carries that month's end (e.g. "2026/08/31").
DEFAULT_PERIOD_END = "2025/02/28"


def _ytd_header(period_end: str = DEFAULT_PERIOD_END) -> list[str]:
    return [
        "Year to Date Detail",
        f"Printed for period ending {period_end}",
        "Printed for Sample Co (Pty) Ltd: Monthly",
        MONTHS_LINE,
    ]


YTD_HEADER = _ytd_header()


def _pdf(pages: list[list]) -> bytes:
    """Each page is a list of lines; a line is a string or [(x, text), ...]."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setFont("Helvetica", 7)
    for lines in pages:
        y = A4[1] - 40
        for line in lines:
            if isinstance(line, str):
                pdf.drawString(20, y, line)
            else:
                for x, text in line:
                    pdf.drawString(x, y, text)
            y -= 12
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _twelve(values: list[str]) -> str:
    return " ".join(values + ["0,00"] * (12 - len(values)))


def ytd_page(code, name, status_line, earnings_total, uif=None,
             period_end: str = DEFAULT_PERIOD_END):
    """One employee page. earnings_total / uif: month values from March on."""
    lines = _ytd_header(period_end) + [
        f"Employee code: {code} Employee name: {name}",
        status_line,
        "Earnings",
        f"Basic salary {_twelve(earnings_total)} 99 999,99",
        f"TOTAL {_twelve(earnings_total)} 99 999,99",
        "Deductions",
        f"Tax {_twelve(['100,00'] * len(earnings_total))} 1 200,00",
    ]
    if uif is not None:
        lines.append(f"Unemployment insurance fund {_twelve(uif)} 600,00")
    lines += [
        "TOTAL 0,00",
        "Company Contributions",
        f"Unemployment insurance fund {_twelve(['777,77'] * 12)} 9 333,24",
        "TOTAL 0,00",
        "Printed on 01/03/2025 08:00 Page 1 of 3",
    ]
    return lines


def ytd_pdf(period_end: str = DEFAULT_PERIOD_END) -> bytes:
    header = _ytd_header(period_end)
    summary = header + [
        "REPORT SUMMARY",
        "Earnings",
        f"TOTAL {_twelve(['1 000,00'] * 12)} 12 000,00",
    ]
    return _pdf([
        ytd_page(
            "007", "Jane Sample",
            "Status: Employed; From: 2020/01/01; Tax status: Statutory Tables; Tax age: 40",
            ["5 139,10", "5 200,00", "5 300,00"],
            uif=["51,39", "52,00", "53,00"],
            period_end=period_end,
        ),
        ytd_page(
            "12", "Leethan Van de Rheede",
            "Status: No longer employed; From: 2024/03/01 To: 2024/05/15; "
            "Tax status: Statutory Tables; Tax age: 33",
            ["8 000,00", "8 000,00"],
        ),
        # A different employee whose code differs from "007" only by a leading
        # zero, as real Sage reports have ("026" and "0026").
        ytd_page(
            "0007", "Sam Other",
            "Status: Employed; From: 2024/04/01; Tax status: Statutory Tables; Tax age: 25",
            ["0,00", "0,00", "4 000,00"],
            uif=["0,00", "0,00", "40,00"],
        ),
        summary,
    ])


def employee_details_pdf() -> bytes:
    def page(code, name, extra):
        return ["Employee Details", f"Employee code {code}", f"Employee name {name}"] + extra

    return _pdf([
        page("007", "Ms J Sample", [
            "ID number 8306056177085",
            "Passport number",
            "Date Engaged 2020/01/01",
            "UIF status Contributes",
            "Average working hours per period 173,33",
        ]),
        page("12", "Mr L Van de Rheede", [
            "Passport number BN487879",
            "Date Engaged 2024/03/01",
            "End date 2024/05/15",
            "UIF status Does not contribute",
        ]),
    ])


def company_details_pdf() -> bytes:
    return _pdf([[
        "Company Details",
        "Company name Sample Co (Pty) Ltd Company number 1",
        "Company registration number 2001/123456/07",
        "PAYE reference number 7123456789",
        "UIF registration number 1234567/8",
        "Residential address 1 Main Road, Paarl",
        "Postal address PO Box 1, Paarl",
        [(20, "SARS"), (300, "UIF")],
        [(20, "Name Left Person"), (300, "Name Right Person")],
        [(20, "Email address left@example.com"), (300, "Email address uif@example.com")],
        [(20, "Telephone number 0210000000"), (300, "Telephone number 0211111111")],
        "Printed on 01/03/2025 08:00",
    ]])


def blank_pdf() -> bytes:
    return _pdf([["Some other report"]])
