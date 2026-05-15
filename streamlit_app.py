"""
UIF-ektief — Streamlit app entry point.

Takes two Sage CSV exports plus a company-config form and produces one or more
downloadable SARS UIF declaration files, one per selected month of the tax year.
No authentication: the app is stateless and processes everything in memory.
"""

import io
import zipfile

import pandas as pd
import streamlit as st

from uif import generate_003, match, parse_employees, parse_ytd, validate
from uif.models import TAX_YEAR_MONTHS, Company, period_code

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
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,wght@0,400;0,500;0,600;1,400;1,500&family=Inter:wght@400;500;600&display=swap');

:root {
    --bg:           oklch(0.97 0.008 75);
    --bg-soft:      oklch(0.94 0.012 75);
    --text:         oklch(0.22 0.012 60);
    --text-muted:   oklch(0.45 0.015 60);
    --accent:       oklch(0.62 0.14 65);
    --accent-deep:  oklch(0.50 0.16 60);
    --line:         oklch(0.88 0.015 70);
}

html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
    background: var(--bg);
}

[data-testid="stAppViewContainer"] *, .stMarkdown, .stMarkdown p,
.stMarkdown li, [data-testid="stWidgetLabel"] {
    font-family: 'Inter', system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    color: var(--text);
}

/* Wordmark and identity ----------------------------------------------------*/
.wordmark {
    font-family: 'Fraunces', Georgia, serif;
    font-size: clamp(2.6rem, 5.5vw, 4.25rem);
    font-weight: 500;
    letter-spacing: -0.035em;
    line-height: 0.95;
    color: var(--text);
    margin: 1.5rem 0 0.4rem 0;
}
.wordmark em {
    font-style: italic;
    font-weight: 400;
    color: var(--accent-deep);
}
.tagline {
    font-family: 'Inter', sans-serif;
    font-size: 1.05rem;
    color: var(--text-muted);
    max-width: 60ch;
    margin: 0 0 2rem 0;
    line-height: 1.5;
}

/* Section headers ----------------------------------------------------------*/
.section-eyebrow {
    font-family: 'Inter', sans-serif;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--accent-deep);
    margin: 2.5rem 0 0.25rem 0;
}
.section-title {
    font-family: 'Fraunces', Georgia, serif;
    font-size: 1.75rem;
    font-weight: 500;
    letter-spacing: -0.015em;
    color: var(--text);
    margin: 0 0 1rem 0;
    line-height: 1.15;
}

/* Streamlit markdown headings get the Fraunces treatment too --------------*/
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3 {
    font-family: 'Fraunces', Georgia, serif !important;
    font-weight: 500 !important;
    letter-spacing: -0.015em !important;
}

/* File uploader: current Streamlit Cloud renders two stacked text spans
   ("upload" twice) inside the button, overlapping. Hide all the button's
   native content and overlay a clean label via a pseudo-element. */
[data-testid="stFileUploader"] button {
    font-size: 0 !important;
    background: var(--bg) !important;
    border: 1px solid var(--line) !important;
    border-radius: 8px !important;
    padding: 0.55rem 1.1rem !important;
    transition: border-color 180ms cubic-bezier(0.22, 1, 0.36, 1),
                background 180ms cubic-bezier(0.22, 1, 0.36, 1) !important;
}
[data-testid="stFileUploader"] button > * {
    display: none !important;
}
[data-testid="stFileUploader"] button::before {
    content: "Choose file" !important;
    font-family: 'Inter', system-ui, sans-serif !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    color: var(--text) !important;
    letter-spacing: 0 !important;
}
[data-testid="stFileUploader"] button:hover {
    border-color: var(--accent) !important;
    background: oklch(0.96 0.018 70) !important;
}

/* Inputs: clean focus rings ------------------------------------------------*/
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] div[role="combobox"],
.stTextInput input {
    border-radius: 8px !important;
    border-color: var(--line) !important;
    background: var(--bg-soft) !important;
}
[data-testid="stTextInput"] input:focus,
.stTextInput input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px oklch(0.62 0.14 65 / 0.18) !important;
}

/* Buttons: accent emphasis for the download action only. Avoid the broader
   primary-button testid because Streamlit reuses it for the file uploader's
   own controls in some versions. */
[data-testid="stDownloadButton"] button {
    background: var(--accent-deep) !important;
    color: white !important;
    font-weight: 600 !important;
    letter-spacing: 0.005em !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.7rem 1.6rem !important;
    transition: background 180ms cubic-bezier(0.22, 1, 0.36, 1),
                transform 180ms cubic-bezier(0.22, 1, 0.36, 1) !important;
}
[data-testid="stDownloadButton"] button:hover {
    background: oklch(0.42 0.16 55) !important;
    transform: translateY(-1px);
}

/* Multiselect chips --------------------------------------------------------*/
[data-baseweb="tag"] {
    background: oklch(0.92 0.04 70) !important;
    color: var(--accent-deep) !important;
    border-radius: 6px !important;
    font-weight: 500 !important;
}

/* Expander headers ---------------------------------------------------------*/
details summary {
    font-family: 'Inter', sans-serif !important;
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
    font-family: 'Inter', sans-serif;
    font-size: 0.85rem;
    color: var(--text-muted);
    margin-top: 3rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--line);
}
</style>
"""
st.markdown(_STYLES, unsafe_allow_html=True)


def section(eyebrow: str, title: str) -> None:
    """Render a typographic section header (eyebrow + Fraunces title)."""
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


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    '<h1 class="wordmark">UIF<em>-ektief</em></h1>'
    '<p class="tagline">SARS UIF declaration files for the months Sage will not '
    "regenerate. Drop in two CSV exports, fill the company details once, pick "
    "the months you need, download.</p>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Upload section
# ---------------------------------------------------------------------------

section("Step 1", "Drop in the Sage exports")

st.markdown(
    "Both files must be from the **same company and same tax year**. Before "
    "uploading the Employee Details CSV, open it in Excel, format column B as "
    "**Number** with 0 decimals, and save. That stops Excel mangling SA ID "
    "numbers into scientific notation."
)

col1, col2 = st.columns(2, gap="large")
with col1:
    ytd_file = st.file_uploader(
        "Year to Date Detail",
        type=["csv"],
        key="ytd_upload",
        help="The payroll YTD report exported from Sage.",
    )
with col2:
    emp_file = st.file_uploader(
        "Employee Details",
        type=["csv"],
        key="emp_upload",
        help="The employee master report with ID/passport numbers, DOBs, dates.",
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

try:
    ytd_data, tax_year_end = _parse_ytd(ytd_file.getvalue())
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not read the Year to Date Detail CSV: {exc}")
    st.stop()

try:
    emp_data = _parse_employees(emp_file.getvalue())
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not read the Employee Details CSV: {exc}")
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
file_extension = cfg_right.text_input(
    "Output file extension", value="003", key="file_extension"
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
    file_extension=file_extension.strip() or "003",
)

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

for month in ordered_months:
    period = period_code(month, tax_year_end)
    blocking, soft = validate.validate(matched, month)
    blocking_total.extend(blocking)
    included = generate_003.included_for_month(matched, month)

    rows = []
    for record in included:
        gross, remuneration, uif_total = generate_003.employee_figures(record, month)
        emp = record.employee
        rows.append(
            {
                "Code": record.employee_code,
                "Name": (
                    f"{emp.first_names} {emp.surname}".strip()
                    if emp
                    else record.ytd.employee_name
                ),
                "ID / Passport": (emp.id_number or emp.passport_number) if emp else "",
                "Gross (8300)": gross,
                "Remuneration (8310)": remuneration,
                "UIF total (8320)": float(uif_total),
                "Status": record.ytd.status,
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

ref_for_name = company.uif_ref.lstrip("0") or company.uif_ref

files: dict[str, bytes] = {}
for month in ordered_months:
    period = period_code(month, tax_year_end)
    content = generate_003.build(matched, month, period, company)
    if len(ordered_months) == 1:
        filename = f"{ref_for_name}.{company.file_extension}"
    else:
        filename = f"{ref_for_name}_{period}.{company.file_extension}"
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
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename, content in files.items():
            archive.writestr(filename, content)
    st.download_button(
        f"Download  {len(files)} files (zip)",
        data=zip_buffer.getvalue(),
        file_name=f"{ref_for_name}_uif_declarations.zip",
        mime="application/zip",
        type="primary",
    )

st.markdown(
    '<p class="fineprint">Files are built in memory and never written to disk. '
    "Close the tab and the data is gone.</p>",
    unsafe_allow_html=True,
)
