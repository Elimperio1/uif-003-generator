"""
UIF-ektief — Streamlit app entry point.

Takes two payroll exports (Sage CSVs or Standard Format workbooks) plus a
company-config form and produces one or more downloadable SARS UIF declaration
files, one per selected month of the tax year.
No authentication: the app is stateless and processes everything in memory.
"""

import io
import zipfile

import pandas as pd
import streamlit as st

from uif import generate_003, match, parse_employees, parse_standard, parse_ytd, validate
from uif import uif_ref as uif_ref_rules  # `uif_ref` is also a form field below
from uif.models import (
    EMPLOYMENT_STATUS_CODES,
    TAX_YEAR_MONTHS,
    Company,
    period_code,
)

st.set_page_config(
    page_title="UIF-ektief",
    page_icon="✦",
    layout="centered",
)


# ---------------------------------------------------------------------------
# Visual layer
# ---------------------------------------------------------------------------

_STYLES = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500&family=Lora:ital,wght@0,400;0,500;0,600;1,400&display=swap');

:root {
    --bg:           oklch(1 0 0);
    --bg-soft:      oklch(0.97 0.012 250);
    --text:         oklch(0.18 0.05 260);
    --text-muted:   oklch(0.45 0.06 255);
    --accent:       oklch(0.42 0.10 255);
    --accent-deep:  oklch(0.32 0.10 255);
    --line:         oklch(0.92 0.012 250);
}

html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
    background: var(--bg);
}

/* Body-level font + colour so it INHERITS naturally to descendants.
   A universal `*` selector forces the font onto Material Icons spans too,
   which makes their icon-name leak out as plain text ("upload",
   "arrow_right" etc). Inheritance lets icon fonts keep their own font. */
body, [data-testid="stAppViewContainer"] {
    font-family: 'Lora', Georgia, 'Times New Roman', serif;
    color: var(--text);
}

/* Wordmark and identity ----------------------------------------------------*/
.wordmark {
    font-family: 'Playfair Display', Georgia, serif;
    font-size: clamp(2.8rem, 5.5vw, 4.5rem);
    font-weight: 700;
    letter-spacing: -0.02em;
    line-height: 1.0;
    color: var(--text);
    margin: 1.5rem 0 0.4rem 0;
}
.wordmark em {
    font-style: italic;
    font-weight: 500;
    color: var(--accent);
}
.tagline {
    font-family: 'Lora', Georgia, serif;
    font-size: 1.1rem;
    color: var(--text-muted);
    max-width: 60ch;
    margin: 0 0 2rem 0;
    line-height: 1.55;
}

/* Section headers ----------------------------------------------------------*/
.section-eyebrow {
    font-family: 'Lora', Georgia, serif;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: var(--accent);
    margin: 2.5rem 0 0.35rem 0;
}
.section-title {
    font-family: 'Playfair Display', Georgia, serif;
    font-size: 1.95rem;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--text);
    margin: 0 0 1rem 0;
    line-height: 1.15;
}

/* Streamlit markdown headings get the Playfair treatment too --------------*/
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3 {
    font-family: 'Playfair Display', Georgia, serif !important;
    font-weight: 600 !important;
    letter-spacing: -0.01em !important;
}

/* File uploader: prominent Playfair label so each upload zone is obvious. */
[data-testid="stFileUploader"] [data-testid="stWidgetLabel"],
[data-testid="stFileUploader"] [data-testid="stWidgetLabel"] *,
[data-testid="stFileUploader"] label,
[data-testid="stFileUploader"] > label {
    font-family: 'Playfair Display', Georgia, serif !important;
    font-size: 1.35rem !important;
    font-weight: 600 !important;
    color: var(--text) !important;
    margin-bottom: 0.5rem !important;
    letter-spacing: -0.005em !important;
}

/* Inputs: clean focus rings ------------------------------------------------*/
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] div[role="combobox"],
.stTextInput input {
    border-radius: 6px !important;
    border-color: var(--line) !important;
    background: var(--bg-soft) !important;
    font-family: 'Lora', Georgia, serif !important;
}
[data-testid="stTextInput"] input:focus,
.stTextInput input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px oklch(0.42 0.10 255 / 0.18) !important;
}

/* Buttons: accent emphasis for the download action only. Avoid the broader
   primary-button testid because Streamlit reuses it for the file uploader's
   own controls in some versions. */
[data-testid="stDownloadButton"] button {
    background: var(--accent-deep) !important;
    color: white !important;
    font-family: 'Playfair Display', Georgia, serif !important;
    font-weight: 600 !important;
    font-size: 1.05rem !important;
    letter-spacing: 0.01em !important;
    border: none !important;
    border-radius: 6px !important;
    padding: 0.75rem 1.8rem !important;
    transition: background 180ms cubic-bezier(0.22, 1, 0.36, 1),
                transform 180ms cubic-bezier(0.22, 1, 0.36, 1) !important;
}
[data-testid="stDownloadButton"] button:hover {
    background: oklch(0.22 0.10 260) !important;
    transform: translateY(-1px);
}

/* Multiselect chips --------------------------------------------------------*/
[data-baseweb="tag"] {
    background: oklch(0.94 0.04 255) !important;
    color: var(--accent-deep) !important;
    border-radius: 4px !important;
    font-weight: 500 !important;
    font-family: 'Lora', Georgia, serif !important;
}

/* Expander headers ---------------------------------------------------------*/
details summary {
    font-family: 'Lora', Georgia, serif !important;
    font-weight: 500 !important;
    color: var(--text) !important;
}

/* Alerts: tuned to palette -------------------------------------------------*/
[data-baseweb="notification"] {
    border-radius: 10px !important;
    border: 1px solid var(--line) !important;
}

/* Hairline rules between major sections -----------------------------------*/
hr {
    border: none;
    border-top: 1px solid var(--line);
    margin: 2.5rem 0 0 0;
}

/* Tighten Streamlit's default top padding so the wordmark lands well ------*/
.block-container {
    padding-top: 2.5rem !important;
}

/* Dataframe: lift slightly, no harsh borders ------------------------------*/
[data-testid="stDataFrame"] {
    border: 1px solid var(--line);
    border-radius: 10px;
    overflow: hidden;
}

/* Footer note style --------------------------------------------------------*/
.fineprint {
    font-family: 'Lora', Georgia, serif;
    font-size: 0.9rem;
    color: var(--text-muted);
    margin-top: 3rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--line);
}
</style>
"""
st.markdown(_STYLES, unsafe_allow_html=True)


def section(eyebrow: str, title: str) -> None:
    """Render a typographic section header (eyebrow + Playfair title)."""
    st.markdown(
        f'<div class="section-eyebrow">{eyebrow}</div>'
        f'<h2 class="section-title">{title}</h2>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Parsing (cached on file bytes)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _parse_ytd(data: bytes):
    return parse_ytd.parse(data), parse_ytd.tax_year_end_year(data)


@st.cache_data(show_spinner=False)
def _parse_employees(data: bytes):
    return parse_employees.parse(data)


@st.cache_data(show_spinner=False)
def _list_year_sheets(data: bytes):
    return parse_standard.list_year_sheets(data)


@st.cache_data(show_spinner=False)
def _parse_standard_ytd(data: bytes, sheet: str):
    return parse_standard.parse_ytd(data, sheet)


@st.cache_data(show_spinner=False)
def _parse_standard_employees(data: bytes):
    return parse_standard.parse_employees(data)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    '<h1 class="wordmark">UIF<em>-ektief</em></h1>'
    '<p class="tagline">SARS UIF declaration files for the months Sage will not '
    "regenerate. Drop in two payroll exports, fill the company details once, pick "
    "the months you need, download.</p>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Upload section
# ---------------------------------------------------------------------------

section("Step 1", "Drop in the payroll files")

st.markdown(
    "Both files must be for the **same company and same tax year**. Two "
    "formats are supported and detected automatically, per file: the Sage "
    "CSV exports, and Standard Format workbooks (.xlsx). For a **Sage "
    "Employee Details CSV** only: open it in Excel first, format column B as "
    "**Number** with 0 decimals, and save. That stops Excel mangling SA ID "
    "numbers into scientific notation."
)

col1, col2 = st.columns(2, gap="large")
with col1:
    ytd_file = st.file_uploader(
        "Year to Date Detail",
        type=["csv", "xlsx"],
        key="ytd_upload",
        help="Sage 'Year to Date Detail' CSV, or a Standard Format payroll "
             "workbook (.xlsx) with one sheet per tax year.",
    )
with col2:
    emp_file = st.file_uploader(
        "Employee Details",
        type=["csv", "xlsx"],
        key="emp_upload",
        help="Sage 'Employee Details' CSV, or the Standard Format employee "
             "master workbook (.xlsx) with an 'Employee details' sheet.",
    )

if not (ytd_file and emp_file):
    st.markdown(
        '<p class="fineprint">Waiting for both files. Nothing leaves your '
        "browser session. The app holds the data in memory and discards it "
        "when you close the tab.</p>",
        unsafe_allow_html=True,
    )
    st.stop()

# ---------------------------------------------------------------------------
# Parse + match
# ---------------------------------------------------------------------------

ytd_bytes = ytd_file.getvalue()
emp_bytes = emp_file.getvalue()
standard_warnings: list[str] = []

try:
    if parse_standard.detect_format(ytd_bytes) == "standard":
        year_sheets = _list_year_sheets(ytd_bytes)
        if not year_sheets:
            st.error(
                "This workbook has no year sheets (tabs named like '2025'). "
                "Is it the payroll workbook?"
            )
            st.stop()
        if len(year_sheets) > 1:
            sheet = st.selectbox(
                "Tax year",
                year_sheets,
                index=None,
                placeholder="Select the tax year",
                format_func=lambda name: f"February {name}",
                key="std_year_sheet",
            )
            if sheet is None:
                st.info("Select the tax year to continue.")
                st.stop()
        else:
            sheet = year_sheets[0]
        ytd_data, standard_warnings = _parse_standard_ytd(ytd_bytes, sheet)
        tax_year_end = parse_standard.tax_year_end_year(sheet)
        hint = parse_standard.read_company_header(ytd_bytes, sheet)
        hint_bits = [
            part for part in (
                hint["company"],
                f"PAYE {hint['paye']}" if hint["paye"] else "",
                f"UIF {hint['uif']}" if hint["uif"] else "",
            ) if part
        ]
        if hint_bits:
            st.markdown(
                f"<p style='color:var(--text-muted);'>Workbook header: "
                f"{' · '.join(hint_bits)}. Enter the official reference "
                f"numbers below; nothing is auto-filled.</p>",
                unsafe_allow_html=True,
            )
    else:
        ytd_data, tax_year_end = _parse_ytd(ytd_bytes)
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not read the payroll file: {exc}")
    st.stop()

try:
    if parse_standard.detect_format(emp_bytes) == "standard":
        emp_data = _parse_standard_employees(emp_bytes)
    else:
        emp_data = _parse_employees(emp_bytes)
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not read the employee details file: {exc}")
    st.stop()

matched, match_warnings = match.join(ytd_data, emp_data)

st.markdown(
    f"<p style='margin-top:1.25rem;color:var(--text-muted);'>"
    f"Read <strong style='color:var(--text);'>{len(ytd_data)}</strong> "
    f"employees from the YTD report and "
    f"<strong style='color:var(--text);'>{len(emp_data)}</strong> from the "
    f"Employee Details report. Tax year ending February "
    f"<strong style='color:var(--text);'>{tax_year_end}</strong>.</p>",
    unsafe_allow_html=True,
)
for warning in match_warnings:
    st.warning(warning)
for warning in standard_warnings:
    st.warning(warning)

# ---------------------------------------------------------------------------
# Company / filer details
# ---------------------------------------------------------------------------

section("Step 2", "Company and filer details")

cfg_left, cfg_right = st.columns(2, gap="large")
uif_ref = cfg_left.text_input("UIF reference number", key="uif_ref")
paye_ref = cfg_right.text_input("PAYE reference number", key="paye_ref")
contact_name = cfg_left.text_input("Filer contact name", key="contact_name")
contact_phone = cfg_right.text_input("Filer contact phone", key="contact_phone")
email_header = cfg_left.text_input("Contact email (file header)", key="email_header")
email_footer = cfg_right.text_input(
    "Contact email (file footer, defaults to header)", key="email_footer"
)
submission_mode = cfg_left.selectbox(
    "Submission mode", ["LIVE", "TEST"], key="submission_mode"
)

_required = {
    "UIF reference number": uif_ref,
    "PAYE reference number": paye_ref,
    "Filer contact name": contact_name,
    "Filer contact phone": contact_phone,
    "Contact email (file header)": email_header,
}
_missing = [name for name, value in _required.items() if not value.strip()]
if _missing:
    st.info("Still need: " + ", ".join(_missing) + ".")
    st.stop()

company = Company(
    uif_ref=uif_ref.strip(),
    paye_ref=paye_ref.strip(),
    contact_name=contact_name.strip(),
    contact_phone=contact_phone.strip(),
    contact_email_header=email_header.strip(),
    contact_email_footer=email_footer.strip() or email_header.strip(),
    submission_mode=submission_mode,
)

normalised_ref = uif_ref_rules.normalise(company.uif_ref)
if normalised_ref != company.uif_ref.strip():
    st.markdown(
        f"<p style='color:var(--text-muted);'>Field 8020 will be sent as "
        f"<strong style='color:var(--text);'>{normalised_ref}</strong> — the "
        f"spec requires 9 digits, zero-filled from the left, with any slash "
        f"or space removed.</p>",
        unsafe_allow_html=True,
    )
for warning in validate.validate_company(company):
    st.warning(warning)

# ---------------------------------------------------------------------------
# Month selection
# ---------------------------------------------------------------------------

section("Step 3", "Pick the months")

months = st.multiselect(
    "Each selected month produces one declaration file.",
    TAX_YEAR_MONTHS,
    key="months",
)
if not months:
    st.info("Select at least one month.")
    st.stop()

# ---------------------------------------------------------------------------
# Preview + validation
# ---------------------------------------------------------------------------

section("Step 4", "Preview")

blocking_total: list[str] = []
ordered_months = sorted(months, key=TAX_YEAR_MONTHS.index)
periods = {month: period_code(month, tax_year_end) for month in ordered_months}

# --- Termination reasons (field 8280) -------------------------------------
# The payroll export only says "Terminated" / "No longer employed", which the
# spec has no code for. Defaulting everyone to 06 Resigned is accepted
# silently by SARS and generally disqualifies a UIF claim, so each one is
# confirmed here instead.
terminations = generate_003.terminations_for_months(matched, ordered_months, periods)
status_overrides: dict[str, str] = {}

if terminations:
    st.markdown(
        f"<p style='margin-bottom:0.75rem;'><strong>{len(terminations)} "
        f"employee(s) are declared as having left.</strong> Field 8280 needs "
        f"the reason. The payroll file cannot tell a resignation from a "
        f"retrenchment, so confirm each one — SARS accepts any valid code "
        f"without complaint, and the wrong one can cost the employee their "
        f"claim.</p>",
        unsafe_allow_html=True,
    )
    status_options = list(EMPLOYMENT_STATUS_CODES)
    for record in terminations:
        emp = record.employee
        name = (
            f"{emp.first_names} {emp.surname}".strip()
            if emp
            else record.ytd.employee_name
        )
        default = generate_003.default_status_code(record)
        left, right = st.columns([1, 1], gap="medium", vertical_alignment="center")
        left.markdown(
            f"<p style='margin:0;'><strong>{record.employee_code}</strong> — "
            f"{name}<br><span style='color:var(--text-muted);font-size:0.85rem;'>"
            f"left {generate_003.termination_date(record) or 'date unknown'}"
            f"</span></p>",
            unsafe_allow_html=True,
        )
        status_overrides[record.employee_code] = right.selectbox(
            f"Reason for {record.employee_code}",
            status_options,
            index=status_options.index(default),
            format_func=lambda code: f"{code} — {EMPLOYMENT_STATUS_CODES[code]}",
            key=f"status_8280_{record.employee_code}",
            label_visibility="collapsed",
        )

    still_resigned = [
        code for code in status_overrides.values() if code == "06"
    ]
    if still_resigned:
        st.warning(
            f"{len(still_resigned)} of these will be declared as "
            f"06 Resigned. Resignation generally disqualifies a UIF claim — "
            f"confirm each is genuinely a resignation before downloading."
        )
    st.markdown("<hr>", unsafe_allow_html=True)

for month in ordered_months:
    period = periods[month]
    blocking, soft = validate.validate(matched, month)
    blocking_total.extend(blocking)
    included = generate_003.included_for_month(matched, month)

    rows = []
    for record in included:
        gross, remuneration, uif_total = generate_003.employee_figures(record, month)
        emp = record.employee
        status_8280 = (
            status_overrides.get(
                record.employee_code, generate_003.default_status_code(record)
            )
            if generate_003.is_terminated_in_period(record, period)
            else "01"
        )
        rows.append(
            {
                "Code": record.employee_code,
                "Name": (
                    f"{emp.first_names} {emp.surname}".strip()
                    if emp
                    else record.ytd.employee_name
                ),
                "ID / Passport / Payroll": (
                    (emp.id_number or emp.passport_number) if emp else ""
                ) or record.employee_code,
                "Gross (8300)": gross,
                "Remuneration (8310)": remuneration,
                "UIF total (8320)": float(uif_total),
                "Status (8280)": (
                    f"{status_8280} — {EMPLOYMENT_STATUS_CODES[status_8280]}"
                ),
            }
        )

    with st.expander(
        f"{month} {period} — {len(included)} employee(s)",
        expanded=(len(months) == 1),
    ):
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.markdown(
                "<p style='color:var(--text-muted);'>No employees had earnings "
                "in this month.</p>",
                unsafe_allow_html=True,
            )
        for error in blocking:
            st.error(error)
        for warning in soft:
            st.warning(warning)

if blocking_total:
    st.error("Resolve the blocking errors above before files can be generated.")
    st.stop()

# ---------------------------------------------------------------------------
# Generate + download
# ---------------------------------------------------------------------------

section("Step 5", "Download")

st.markdown(
    "The file number is the `.nnn` on the end of the filename. **If the Fund "
    "receives two files with the same name, the later one overwrites the "
    "earlier one entirely** — so a second batch under this reference must "
    "start above the highest number already submitted."
)
start_number = int(
    st.number_input(
        "Starting file number",
        min_value=1,
        max_value=1000 - len(ordered_months),
        value=1,
        step=1,
        key="start_sequence",
        help="Numbers run consecutively from here, one per selected month, "
             "in March-first order.",
    )
)

files: dict[str, bytes] = {}
for sequence, month in enumerate(ordered_months, start=start_number):
    content = generate_003.build(
        matched, month, periods[month], company, status_overrides
    )
    filename = generate_003.build_filename(company.uif_ref, sequence)
    files[filename] = content

if len(files) == 1:
    ((filename, content),) = files.items()
    st.download_button(
        f"Download  {filename}",
        data=content,
        file_name=filename,
        mime="text/plain",
        type="primary",
    )
else:
    first_period = periods[ordered_months[0]]
    last_period = periods[ordered_months[-1]]
    zip_filename = (
        f"{normalised_ref[-8:]}-uif-{first_period}-to-{last_period}.zip"
    )
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename, content in files.items():
            archive.writestr(filename, content)
    st.download_button(
        f"Download  {len(files)} files (zip)",
        data=zip_buffer.getvalue(),
        file_name=zip_filename,
        mime="application/zip",
        type="primary",
    )

st.markdown(
    '<p class="fineprint">Files are built in memory and never written to disk. '
    "Close the tab and the data is gone.</p>",
    unsafe_allow_html=True,
)
