"""
Readers for the Sage report PDFs (UI-19 mode only).

Ported from the standalone script UI19_Automation_7/sage_reader.py:
parse_ytd_detail, parse_employee_detail and parse_company_detail, with their
regexes and page-detection tests unchanged. The script's readers take a file
path and return plain dicts; here they take the uploaded bytes, and thin
adapters turn the result into the YtdRecord / EmployeeRecord the app's UI-19
rules (uif/ui19.py) already consume.

The YTD PDF carries only each employee's Earnings TOTAL line, not the line
items the eDecs remuneration rules need, so these readers are not used for
the eDecs file.

Employee codes are kept exactly as printed, as the script does. Real Sage
reports hold distinct employees coded "026" and "0026", which the CSV
parsers' leading-zero normalisation would merge into one. So a PDF report
only pairs with another PDF report.
"""

from __future__ import annotations

import io
import re

import pdfplumber

from .models import MONTH_NUMBER, TAX_YEAR_MONTHS, EmployeeRecord, YtdRecord
from .parse_ytd import _slash_date_to_yyyymmdd
from .ui19 import split_employee_detail_name

# --- Year to Date Detail (script: parse_ytd_detail) ------------------------

MONTH_NAME_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b",
    re.IGNORECASE,
)
EMP_LINE_RE = re.compile(r"Employee code:\s*(?P<code>\S+).*?Employee name:\s*(?P<name>.+)")
STATUS_LINE_RE = re.compile(
    r"Status:\s*(?P<status>[^;]+);\s*From:\s*(?P<from>\d{4}/\d{2}/\d{2})"
    r"(?:\s+To:\s*(?P<to>\d{4}/\d{2}/\d{2}))?"
)
PERIOD_END_RE = re.compile(r"Printed for period ending\s*(\d{4}/\d{2}/\d{2})")
# Space-grouped thousands and either decimal separator ("5 139,10" / "5 139.10").
YTD_NUMBER_RE = re.compile(r"-?\d{1,3}(?:\s\d{3})*[.,]\d{2}")
SECTION_NAMES = ("Earnings", "Deductions", "Company Contributions",
                 "Fringe Benefits", "Tax Deductible Deductions", "Other Totals")

# --- Employee Details (script: parse_employee_detail) ----------------------

# Every field is matched on its own line with [ \t]+, never \s+, so a blank
# field cannot swallow the next line's label.
EMPDETAIL_CODE_RE = re.compile(r"Employee code\s+(?P<code>\S+)")
EMPDETAIL_NAME_RE = re.compile(r"Employee name\s+(?P<name>.+)")
EMPDETAIL_ID_RE = re.compile(r"ID number[ \t]+(?P<id>\d{6,13})\b")
EMPDETAIL_PASSPORT_RE = re.compile(r"Passport number[ \t]+(?P<passport>(?!Passport\b)[A-Za-z0-9]+)\b")
EMPDETAIL_DATE_ENGAGED_RE = re.compile(r"Date Engaged[ \t]+(?P<engaged>\d{4}/\d{2}/\d{2})\b")
EMPDETAIL_END_DATE_RE = re.compile(r"End date[ \t]+(?P<end>\d{4}/\d{2}/\d{2})\b")
EMPDETAIL_UIF_RE = re.compile(r"UIF status[ \t]+(?P<status>.+)")
EMPDETAIL_HOURS_RE = re.compile(r"Average working hours per period[ \t]+(?P<hours>[\d.,]+)\b")

# --- Company Details (script: parse_company_detail) ------------------------

# x-position between the SARS contact column (left) and the UIF contact column
# (right), measured by the script on a real Sage "Company Details" report.
CONTACT_COLUMN_SPLIT_X = 250


def is_pdf(data: bytes) -> bool:
    return data[:5] == b"%PDF-"


def _first_page_text(data: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return pdf.pages[0].extract_text() or ""
    except Exception:  # noqa: BLE001 - an unreadable PDF is simply "not a Sage report"
        return ""


def report_kind(data: bytes) -> str | None:
    """'ytd', 'employee_details', 'company_details', or None (script's page tests)."""
    text = _first_page_text(data)
    if "Company Details" in text and "PAYE reference number" in text:
        return "company_details"
    if "Employee Details" in text and "Employee code" in text and "Employee code:" not in text:
        return "employee_details"
    if "Year to Date Detail" in text or ("Employee code:" in text and "Employee name:" in text):
        return "ytd"
    return None


def _ytd_section_bounds(lines):
    idx = {}
    for i, line in enumerate(lines):
        key = line.strip()
        if key in SECTION_NAMES and key not in idx:
            idx[key] = i
    ordered = sorted(idx.items(), key=lambda kv: kv[1])
    bounds = {}
    for i, (name, start) in enumerate(ordered):
        end = ordered[i + 1][1] if i + 1 < len(ordered) else len(lines)
        bounds[name] = (start, end)
    return bounds


def _ytd_numbers(line):
    if not line:
        return []
    return [float(v.replace(" ", "").replace(",", ".")) for v in YTD_NUMBER_RE.findall(line)]


def _parse_ytd_detail(data: bytes) -> dict:
    """The script's parse_ytd_detail, reading bytes instead of a path."""
    month_order = None
    period_end = None
    records = []

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            page.close()  # drop the page's cached objects: ~200 MB peak -> ~8 MB on 68 pages
            if not text.strip():
                continue

            if month_order is None:
                m = PERIOD_END_RE.search(text)
                if m:
                    period_end = m.group(1)
                for line in text.split("\n"):
                    if len(MONTH_NAME_RE.findall(line)) >= 12:
                        month_order = line.split()[:12]
                        break

            emp_match = EMP_LINE_RE.search(text)
            if not emp_match:
                continue  # not an employee page (e.g. the REPORT SUMMARY page)
            status_match = STATUS_LINE_RE.search(text)

            lines = text.split("\n")
            bounds = _ytd_section_bounds(lines)

            earnings_total_line = None
            if "Earnings" in bounds:
                s, e = bounds["Earnings"]
                for line in lines[s:e]:
                    if line.strip().startswith("TOTAL"):
                        earnings_total_line = line  # last TOTAL line in the section wins

            uif_line = None
            if "Deductions" in bounds:
                s, e = bounds["Deductions"]
                for line in lines[s:e]:
                    if line.strip().lower().startswith("unemployment insurance fund"):
                        uif_line = line
                        break

            records.append({
                "code": emp_match.group("code"),
                "name": emp_match.group("name").strip(),
                "status": status_match.group("status").strip() if status_match else "",
                "from_date": status_match.group("from") if status_match else None,
                "to_date": status_match.group("to") if status_match else None,
                "earnings_by_month": _ytd_numbers(earnings_total_line),
                "uif_by_month": _ytd_numbers(uif_line),
            })

    return {"month_order": month_order or [], "period_end": period_end, "records": records}


def tax_year_end_year(data: bytes) -> int:
    """Year of the 'Printed for period ending' date (page 1), as for the YTD CSV."""
    m = PERIOD_END_RE.search(_first_page_text(data))
    if not m:
        raise ValueError("Could not find the 'Printed for period ending' line in the YTD PDF.")
    return int(m.group(1)[:4])


def parse_ytd(data: bytes) -> tuple[dict[str, YtdRecord], list[str]]:
    """Sage Year to Date Detail PDF -> ({employee_code: YtdRecord}, warnings)."""
    if report_kind(data) != "ytd":
        raise ValueError("This PDF is not a Sage 'Year to Date Detail' report.")
    parsed = _parse_ytd_detail(data)
    months = [m.capitalize() for m in parsed["month_order"]]
    if not months or any(m not in MONTH_NUMBER for m in months):
        raise ValueError("Could not find the month-header row in the YTD PDF.")

    records: dict[str, YtdRecord] = {}
    warnings: list[str] = []
    for rec in parsed["records"]:
        code = rec["code"]
        earnings ={m: {} for m in TAX_YEAR_MONTHS}
        for month, amount in zip(months, rec["earnings_by_month"]):
            if amount:
                earnings[month]["TOTAL"] = amount
        if not rec["earnings_by_month"]:
            warnings.append(
                f"{rec['name']}: could not read a gross remuneration figure from "
                f"this report."
            )
        records[code] = YtdRecord(
            employee_code=code,
            employee_name=rec["name"],
            status=rec["status"],
            end_date=_slash_date_to_yyyymmdd(rec["to_date"] or ""),
            earnings=earnings,
            start_date=_slash_date_to_yyyymmdd(rec["from_date"] or ""),
            uif_deducted=dict(zip(months, rec["uif_by_month"])),
        )
    return records, warnings


def parse_employees(data: bytes) -> dict[str, EmployeeRecord]:
    """Sage Employee Details PDF -> {employee_code: EmployeeRecord} (script's reader)."""
    if report_kind(data) != "employee_details":
        raise ValueError("This PDF is not a Sage 'Employee Details' report.")
    out: dict[str, EmployeeRecord] = {}
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            page.close()
            code_match = EMPDETAIL_CODE_RE.search(text)
            if not code_match:
                continue  # not an employee page
            code = code_match.group("code")

            name_match = EMPDETAIL_NAME_RE.search(text)
            employee_name = name_match.group("name").strip() if name_match else ""
            surname, _ = split_employee_detail_name(employee_name)

            id_match = EMPDETAIL_ID_RE.search(text)
            passport_match = EMPDETAIL_PASSPORT_RE.search(text)
            engaged_match = EMPDETAIL_DATE_ENGAGED_RE.search(text)
            end_match = EMPDETAIL_END_DATE_RE.search(text)
            uif_match = EMPDETAIL_UIF_RE.search(text)

            hours = None
            hours_match = EMPDETAIL_HOURS_RE.search(text)
            if hours_match:
                try:
                    hours = float(hours_match.group("hours").replace(",", "."))
                except ValueError:
                    hours = None

            out[code] = EmployeeRecord(
                employee_code=code,
                surname=surname,
                first_names="",
                id_number=id_match.group("id") if id_match else "",
                passport_number=passport_match.group("passport") if passport_match else "",
                date_of_birth="",
                date_engaged=_slash_date_to_yyyymmdd(engaged_match.group("engaged")) if engaged_match else "",
                end_date=_slash_date_to_yyyymmdd(end_match.group("end")) if end_match else "",
                employee_status="",
                uif_status=uif_match.group("status").strip() if uif_match else "",
                employee_name=employee_name,
                average_hours=hours,
            )
    return out


def _words_to_lines(words):
    """Rebuild text lines from pdfplumber words, so one column reads on its own."""
    rows = {}
    for w in words:
        rows.setdefault(round(w["top"]), []).append(w)
    lines = []
    for key in sorted(rows):
        row = sorted(rows[key], key=lambda w: w["x0"])
        lines.append(" ".join(w["text"] for w in row))
    return "\n".join(lines)


def parse_company(data: bytes) -> dict[str, str]:
    """
    Sage Company Details PDF -> the UI-19 employer fields it could read, keyed
    by the app's form field names. Fields it can't read are absent.
    """
    if report_kind(data) != "company_details":
        raise ValueError("This PDF is not a Sage 'Company Details' report.")
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        page = pdf.pages[0]
        text = page.extract_text() or ""
        words = page.extract_words()

    out: dict[str, str] = {}

    m = re.search(r"Company name[ \t]*(.*?)[ \t]*Company number\b", text)
    if m and m.group(1).strip():
        out["trading_name"] = m.group(1).strip()
    for field, pattern in (
        ("cipro_no", r"Company registration number[ \t]+(\S.*)"),
        ("paye_ref", r"PAYE reference number[ \t]+(\S.*)"),
        ("uif_ref", r"UIF registration number[ \t]+(\S.*)"),
        ("physical_address", r"Residential address[ \t]+(.+)"),
        ("postal_address", r"Postal address[ \t]+(.+)"),
    ):
        m = re.search(pattern, text)
        if m:
            out[field] = m.group(1).strip()

    # Contact Details is two columns (SARS contact | UIF contact); the form's
    # employer contact is the UIF one on the right.
    sars_header_top = next((w["top"] for w in words if w["text"] == "SARS"), None)
    footer_top = next((w["top"] for w in words if w["text"] == "Printed"), None)
    if sars_header_top is not None:
        contact_words = [w for w in words if w["top"] > sars_header_top
                         and (footer_top is None or w["top"] < footer_top)]
        right_text = _words_to_lines([w for w in contact_words if w["x0"] >= CONTACT_COLUMN_SPLIT_X])
        for field, pattern in (
            ("contact_name", r"^Name[ \t]+(.+)$"),
            ("email_header", r"^Email address[ \t]+(.+)$"),
            ("contact_phone", r"^Telephone number[ \t]+(.+)$"),
        ):
            m = re.search(pattern, right_text, re.MULTILINE)
            if m:
                out[field] = m.group(1).strip()

    return out
