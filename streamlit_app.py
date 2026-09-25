"""
UIF-ektief — Streamlit app entry point.

Takes two payroll exports (Sage CSVs or Standard Format workbooks; for the
UI-19 form also the Sage report PDFs) plus a company-config form and produces
one or more downloadable SARS UIF declaration files, one per selected month of
the tax year.
No authentication: the app is stateless and processes everything in memory.
"""

import hashlib
import io
import zipfile

import pandas as pd
import streamlit as st

from uif import (
    generate_003,
    match,
    parse_employees,
    parse_sage_pdf,
    parse_standard,
    parse_ytd,
    ui19,
    ui19_pdf,
    validate,
)
from uif import uif_ref as uif_ref_rules  # `uif_ref` is also a form field below
from uif.models import (
    EMPLOYMENT_STATUS_CODES,
    TAX_YEAR_MONTHS,
    Company,
    MatchedRecord,
    period_code,
)

st.set_page_config(
    page_title="UIF-ektief",
    page_icon="✦",
    layout="centered",
)

# Nobody reaches this tool except through the practice-management app's Tools
# menu, which mints a 120-second signed link. Must stay directly under
# set_page_config and above everything else: anything placed earlier runs for
# a visitor who never signed in.
from app_link import require_app_link  # noqa: E402

require_app_link()


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

/* Output mode picker: large cards so the choice is obvious up front --------*/
.st-key-output_mode [role="radiogroup"] {
    gap: 1rem !important;
    flex-wrap: wrap;
}
.st-key-output_mode [role="radiogroup"] > label {
    flex: 1 1 16rem;
    align-items: flex-start;
    padding: 1rem 1.25rem !important;
    margin: 0 !important;
    border: 1px solid var(--line);
    border-radius: 10px;
    background: var(--bg-soft);
    cursor: pointer;
    transition: border-color 180ms cubic-bezier(0.22, 1, 0.36, 1),
                box-shadow 180ms cubic-bezier(0.22, 1, 0.36, 1);
}
.st-key-output_mode [role="radiogroup"] > label:hover {
    border-color: var(--accent);
}
.st-key-output_mode [role="radiogroup"] > label:has(input:checked) {
    border-color: var(--accent);
    box-shadow: 0 0 0 2px oklch(0.42 0.10 255 / 0.25);
    background: var(--bg);
}
.st-key-output_mode [role="radiogroup"] > label [data-testid="stMarkdownContainer"] p {
    font-family: 'Playfair Display', Georgia, serif;
    font-size: 1.3rem;
    font-weight: 600;
    color: var(--text);
}
.st-key-output_mode [role="radiogroup"] > label [data-testid="stCaptionContainer"] p,
.st-key-output_mode [role="radiogroup"] > label small {
    font-size: 0.92rem;
    font-weight: 400;
    color: var(--text-muted);
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


# Details typed in one output mode must survive a switch to the other, but
# Streamlit drops a widget's state on any run that doesn't draw it. So every
# form widget gets a per-mode key and is seeded from this plain dict, which
# each run writes back to.
def kept() -> dict:
    return st.session_state.setdefault("kept_details", {})


def mode_key(field: str) -> str:
    # The "~N" generation suffix appears once code rewrites stored details (the
    # Company Details PDF): new keys make every widget re-seed from kept(), the
    # same way a mode switch does. Generation 0 keeps the original key.
    generation = st.session_state.get("form_generation", 0)
    suffix = st.session_state.get("output_mode", "") + (f"~{generation}" if generation else "")
    st.session_state["drawn_suffix"] = suffix  # what the harvest below reads next run
    return f"{field}@{suffix}"


def kept_text_input(container, label: str, field: str) -> str:
    value = container.text_input(label, value=kept().get(field, ""), key=mode_key(field))
    kept()[field] = value
    return value


# Before anything is drawn: a value typed just before clicking the mode switch
# arrives in the same run as the switch, when its widget is no longer drawn.
# Harvest the last-drawn widgets' values into the store first so none is lost.
# Only those widgets: keys of a mode (or generation) not drawn since linger in
# session state with old values, and reading them made the result depend on
# key order (an edit in one mode could be undone by a switch back).
_drawn_suffix = st.session_state.get("drawn_suffix")
for _key, _value in list(st.session_state.items()):
    if "@" in _key and _value is not None and _key.split("@", 1)[1] == _drawn_suffix:
        kept()[_key.split("@", 1)[0]] = _value


def termination_picker(record: MatchedRecord, end_date: str) -> str | None:
    """Reason-for-leaving selectbox (8280 codes), shared by both output modes."""
    emp = record.employee
    name = (
        f"{emp.first_names} {emp.surname}".strip()
        if emp
        else record.ytd.employee_name
    )
    # No default: a pre-selected 06 with an amber count is exactly what gets
    # clicked past, and a wrong 06 silently costs an ex-employee their claim.
    # The one exception is a code the payroll file itself justifies — a
    # death — which arrives pre-selected as 02 Deceased for confirmation.
    inferred = generate_003.inferred_status_code(record)
    status_options = list(EMPLOYMENT_STATUS_CODES)
    left, right = st.columns([1, 1], gap="medium", vertical_alignment="center")
    left.markdown(
        f"<p style='margin:0;'><strong>{record.employee_code}</strong> — "
        f"{name}<br><span style='color:var(--text-muted);font-size:0.85rem;'>"
        f"left {end_date or 'date unknown'}"
        f"</span></p>",
        unsafe_allow_html=True,
    )
    field = f"status_8280_{record.employee_code}"
    chosen = kept().get(field) or inferred
    selected = right.selectbox(
        f"Reason for {record.employee_code}",
        status_options,
        index=status_options.index(chosen) if chosen else None,
        placeholder="Select the reason for leaving",
        format_func=lambda code: f"{code} — {EMPLOYMENT_STATUS_CODES[code]}",
        key=mode_key(field),
        label_visibility="collapsed",
    )
    if selected is not None:
        kept()[field] = selected
    return selected


def pick_months() -> list[str]:
    """Step 3, shared by both output modes. Stops the run until one is picked."""
    section("Step 3", "Pick the months")
    months = st.multiselect(
        "Each selected month produces one declaration file.",
        TAX_YEAR_MONTHS,
        default=kept().get("months", []),
        key=mode_key("months"),
    )
    kept()["months"] = months
    if not months:
        st.info("Select at least one month.")
        st.stop()
    return months


# ---------------------------------------------------------------------------
# Parsing (cached on file bytes)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _parse_ytd(data: bytes):
    return parse_ytd.parse(data), parse_ytd.tax_year_end_year(data)


@st.cache_data(show_spinner=False)
def _parse_employees(data: bytes):
    return parse_employees.parse(data)


@st.cache_data(show_spinner="Reading the Year to Date Detail PDF...")
def _parse_pdf_ytd(data: bytes):
    records, warnings = parse_sage_pdf.parse_ytd(data)
    return records, parse_sage_pdf.tax_year_end_year(data), warnings


@st.cache_data(show_spinner="Reading the Employee Details PDF...")
def _parse_pdf_employees(data: bytes):
    return parse_sage_pdf.parse_employees(data)


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

section("Start here", "What do you want to produce?")
output_mode = st.radio(
    "Output",
    ["eDecs file (.NNN)", "UI-19 PDF form"],
    captions=[
        "Electronic declaration file to upload to SARS uFiling.",
        "The official UI-19 form, filled in, to sign and send to Labour.",
    ],
    horizontal=True,
    key="output_mode",
    label_visibility="collapsed",
)
ui19_mode = output_mode == "UI-19 PDF form"

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
if ui19_mode:
    st.markdown(
        "For the UI-19 form you can also drop in the **Sage report PDFs** "
        "instead: Year to Date Detail and Employee Details, both as PDFs. A "
        "Company Details PDF fills in the employer details below."
    )

# The uploaders accept PDFs in both modes, so switching mode never clears an
# uploaded file; the eDecs path refuses PDFs further down.
col1, col2 = st.columns(2, gap="large")
with col1:
    ytd_file = st.file_uploader(
        "Year to Date Detail",
        type=["csv", "xlsx", "pdf"],
        key="ytd_upload",
        help="Sage 'Year to Date Detail' CSV or PDF (PDF: UI-19 form only), or "
             "a Standard Format payroll workbook (.xlsx) with one sheet per tax year.",
    )
with col2:
    emp_file = st.file_uploader(
        "Employee Details",
        type=["csv", "xlsx", "pdf"],
        key="emp_upload",
        help="Sage 'Employee Details' CSV or PDF (PDF: UI-19 form only), or the "
             "Standard Format employee master workbook (.xlsx) with an "
             "'Employee details' sheet.",
    )

# UI-19 employer details: filled from a Company Details PDF, once per file,
# and only into fields that are still empty. Bumping form_generation re-keys
# the form widgets so the drawn inputs pick up the new values.
if ui19_mode:
    company_file = st.file_uploader(
        "Company Details (optional)",
        type=["pdf"],
        key="company_upload",
        help="Sage 'Company Details' report PDF. Fills in the trading name, "
             "reference numbers, addresses and UIF contact.",
    )
    if company_file is not None:
        company_bytes = company_file.getvalue()
        company_digest = hashlib.sha256(company_bytes).hexdigest()
        if parse_sage_pdf.report_kind(company_bytes) != "company_details":
            st.error("That PDF is not a Sage 'Company Details' report.")
        elif st.session_state.get("company_pdf_applied") != company_digest:
            filled = []
            for field, value in parse_sage_pdf.parse_company(company_bytes).items():
                if not kept().get(field, "").strip():
                    kept()[field] = value
                    filled.append(field)
            if filled:
                st.session_state["form_generation"] = st.session_state.get("form_generation", 0) + 1
            st.session_state["company_pdf_applied"] = company_digest
            st.session_state["company_pdf_filled"] = len(filled)
        if st.session_state.get("company_pdf_applied") == company_digest:
            st.caption(
                f"Company Details PDF read: filled "
                f"{st.session_state.get('company_pdf_filled', 0)} empty employer "
                f"field(s). Fields you had already typed were left alone."
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
ytd_is_pdf = parse_sage_pdf.is_pdf(ytd_bytes)
emp_is_pdf = parse_sage_pdf.is_pdf(emp_bytes)

if ytd_is_pdf or emp_is_pdf:
    if not ui19_mode:
        st.error(
            "PDF reports only work for the UI-19 PDF form. For the eDecs file, "
            "upload the Sage CSV exports or the Standard Format workbooks."
        )
        st.stop()
    if not (ytd_is_pdf and emp_is_pdf):
        # PDF codes are kept as printed ("026" and "0026" are different
        # employees); the CSV parsers drop leading zeros, so the two can't join.
        st.error(
            "Upload both reports as PDFs, or both as CSV/xlsx. A PDF report "
            "can't be matched against a CSV or workbook."
        )
        st.stop()
    expected = {"Year to Date Detail": (ytd_bytes, "ytd"),
                "Employee Details": (emp_bytes, "employee_details")}
    for label, (data, kind) in expected.items():
        if parse_sage_pdf.report_kind(data) != kind:
            st.error(
                f"The {label} PDF is not a Sage '{label}' report. Check the two "
                f"files are in the right boxes."
            )
            st.stop()
    try:
        ytd_data, tax_year_end, standard_warnings = _parse_pdf_ytd(ytd_bytes)
        emp_data = _parse_pdf_employees(emp_bytes)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not read the PDF reports: {exc}")
        st.stop()

else:
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
# UI-19 output mode (Steps 2-5). Follows the standalone UI19 script's rules
# (uif/ui19.py); none of the eDecs validation below applies to it.
# ---------------------------------------------------------------------------

def run_ui19_steps(ytd_data, emp_data, tax_year_end: int) -> None:
    """Employer details, month pick, preview with H/J codes, PDF download."""
    cfg_left, cfg_right = st.columns(2, gap="large")
    uif_ref = kept_text_input(cfg_left, "UIF reference number", "uif_ref")
    trading_name = kept_text_input(cfg_right, "Trading name", "trading_name")
    paye_ref = kept_text_input(cfg_left, "PAYE reference number", "paye_ref")
    cipro_no = kept_text_input(cfg_right, "Company registration (CIPRO) number", "cipro_no")
    branch_no = kept_text_input(cfg_left, "Branch number", "branch_no")
    authorised = kept_text_input(cfg_right, "Authorised person", "contact_name")
    phone = kept_text_input(cfg_left, "Telephone number", "contact_phone")
    email = kept_text_input(cfg_right, "Email address", "email_header")
    fax = kept_text_input(cfg_left, "Fax number", "fax_no")
    physical = kept_text_input(st, "Physical address", "physical_address")
    postal = kept_text_input(st, "Postal address", "postal_address")
    work = kept_text_input(
        st, "Work address (if different to the physical address)", "work_address"
    )
    decl_left, decl_right = st.columns(2, gap="large")
    decl_name = kept_text_input(
        decl_left, "Declaration: name of the person signing", "decl_name"
    )
    decl_id = kept_text_input(decl_right, "Declaration: their ID number", "decl_id")

    missing = [
        name for name, value in
        {"UIF reference number": uif_ref, "Trading name": trading_name}.items()
        if not value.strip()
    ]
    if missing:
        st.info("Still need: " + ", ".join(missing) + ".")
        st.stop()

    employer = ui19_pdf.Employer(
        uif_employer_ref=uif_ref.strip(),
        trading_name=trading_name.strip(),
        branch_no=branch_no.strip(),
        paye_ref=paye_ref.strip(),
        cipro_no=cipro_no.strip(),
        physical_address=physical.strip(),
        work_address=work.strip(),
        postal_address=postal.strip(),
        email=email.strip(),
        fax_no=fax.strip(),
        phone_no=phone.strip(),
        authorised_person=authorised.strip(),
        declaration_employer_name=decl_name.strip(),
        declaration_employer_id_number=decl_id.strip(),
    )

    months = pick_months()

    section("Step 4", "Preview")
    ordered_months = sorted(months, key=TAX_YEAR_MONTHS.index)
    periods = {month: period_code(month, tax_year_end) for month in ordered_months}
    month_rows = {
        month: ui19.form_rows(ytd_data, emp_data, month, periods[month])
        for month in ordered_months
    }

    # Column H: the same picks, and widget keys, as the eDecs Step 4.
    leavers: dict[str, ui19.FormRow] = {}
    for month in ordered_months:
        for row in month_rows[month][0]:
            if ui19.needs_termination_reason(row, periods[month]):
                leavers.setdefault(row.employee_code, row)
    status_overrides: dict[str, str] = {}
    if leavers:
        st.markdown(
            f"<p style='margin-bottom:0.75rem;'><strong>{len(leavers)} "
            f"employee(s) have left.</strong> Column H of the UI-19 needs the "
            f"reason for termination. The payroll file cannot tell a "
            f"resignation from a retrenchment, so confirm each one.</p>",
            unsafe_allow_html=True,
        )
        for code, row in leavers.items():
            record = MatchedRecord(code, emp_data.get(code), ytd_data[code])
            selected = termination_picker(record, row.termination_date)
            if selected is not None:
                status_overrides[code] = selected
        st.markdown("<hr>", unsafe_allow_html=True)

    # Column J: one pick per non-contributor per month.
    reason_options = list(ui19.NON_CONTRIBUTOR_REASONS)
    j_overrides: dict[str, dict[str, str]] = {month: {} for month in ordered_months}
    non_contributors = [
        (month, row)
        for month in ordered_months
        for row in month_rows[month][0]
        if row.uif_contributor == "NO"
    ]
    if non_contributors:
        st.markdown(
            f"<p style='margin-bottom:0.75rem;'><strong>{len(non_contributors)} "
            f"non-contributor row(s).</strong> Column J needs the reason for "
            f"non-contribution.</p>",
            unsafe_allow_html=True,
        )
        for month, row in non_contributors:
            field = f"ui19_j_{periods[month]}_{row.employee_code}"
            chosen = kept().get(field) or ui19.default_non_contributor_reason(row)
            left, right = st.columns([1, 1], gap="medium", vertical_alignment="center")
            left.markdown(
                f"<p style='margin:0;'><strong>{row.employee_code}</strong> — "
                f"{row.initials} {row.surname}<br><span style='color:var(--text-muted);"
                f"font-size:0.85rem;'>{month} {periods[month][:4]}</span></p>",
                unsafe_allow_html=True,
            )
            selected = right.selectbox(
                f"Non-contribution reason for {row.employee_code} in {month}",
                reason_options,
                index=reason_options.index(chosen) if chosen else None,
                placeholder="Select the reason for non-contribution",
                format_func=lambda c: f"{c}: {ui19.NON_CONTRIBUTOR_REASONS[c]}",
                key=mode_key(field),
                label_visibility="collapsed",
            )
            if selected is not None:
                kept()[field] = selected
                j_overrides[month][row.employee_code] = selected
        st.markdown("<hr>", unsafe_allow_html=True)

    for month in ordered_months:
        rows, warnings = month_rows[month]
        ui19.apply_codes(rows, periods[month], status_overrides, j_overrides[month])
        with st.expander(
            f"{month} {periods[month][:4]} — {len(rows)} employee(s)",
            expanded=(len(months) == 1),
        ):
            if rows:
                st.dataframe(
                    pd.DataFrame([
                        {
                            "Code": r.employee_code,
                            "Surname": r.surname,
                            "Initials": r.initials,
                            "ID / Passport": r.id_number,
                            "Gross": r.gross,
                            "Hours": r.hours_worked,
                            "Start": r.commencement_date,
                            "End": r.termination_date,
                            "H": r.termination_reason_code,
                            "UIF": r.uif_contributor,
                            "J": r.non_contributor_reason_code,
                        }
                        for r in rows
                    ]),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.markdown(
                    "<p style='color:var(--text-muted);'>No employees on the "
                    "payroll this month.</p>",
                    unsafe_allow_html=True,
                )
            for warning in warnings:
                st.warning(warning)

    unset_h = [code for code in leavers if code not in status_overrides]
    unset_j = [
        row.employee_code
        for month, row in non_contributors
        if row.employee_code not in j_overrides[month]
    ]
    if unset_h or unset_j:
        st.error(
            "Select a reason for every employee who has left (column H) and "
            "every non-contributor (column J) before the form can be generated."
        )
        st.stop()

    section("Step 5", "Download")
    st.markdown(
        "Check the PDF against the payroll reports, **sign it**, then submit it "
        "the way you normally submit a UI-19. The signature is left blank."
    )
    pdfs: dict[str, bytes] = {}
    for month in ordered_months:
        year = periods[month][:4]
        pdfs[f"UI19_{month}_{year}.pdf"] = ui19_pdf.write_pdf(
            employer, month_rows[month][0], f"{month} {year}"
        )

    if len(pdfs) == 1:
        ((filename, content),) = pdfs.items()
        st.download_button(
            f"Download  {filename}",
            data=content,
            file_name=filename,
            mime="application/pdf",
            type="primary",
        )
    else:
        first, last = ordered_months[0], ordered_months[-1]
        zip_filename = (
            f"UI19_{first}_{periods[first][:4]}_to_{last}_{periods[last][:4]}.zip"
        )
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for filename, content in pdfs.items():
                archive.writestr(filename, content)
        st.download_button(
            f"Download  {len(pdfs)} forms (zip)",
            data=zip_buffer.getvalue(),
            file_name=zip_filename,
            mime="application/zip",
            type="primary",
        )

    st.markdown(
        '<p class="fineprint">Forms are built in memory and never written to '
        "disk. Close the tab and the data is gone.</p>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Company / filer details
# ---------------------------------------------------------------------------

section("Step 2", "Company and filer details")

if ui19_mode:
    run_ui19_steps(ytd_data, emp_data, tax_year_end)
    st.stop()

cfg_left, cfg_right = st.columns(2, gap="large")
uif_ref = kept_text_input(cfg_left, "UIF reference number", "uif_ref")
paye_ref = kept_text_input(cfg_right, "PAYE reference number", "paye_ref")
contact_name = kept_text_input(cfg_left, "Filer contact name", "contact_name")
contact_phone = kept_text_input(cfg_right, "Filer contact phone", "contact_phone")
email_header = kept_text_input(cfg_left, "Contact email (file header)", "email_header")
email_footer = kept_text_input(
    cfg_right, "Contact email (file footer, defaults to header)", "email_footer"
)
_submission_modes = ["LIVE", "TEST"]
submission_mode = cfg_left.selectbox(
    "Submission mode",
    _submission_modes,
    index=_submission_modes.index(kept().get("submission_mode", "LIVE")),
    key=mode_key("submission_mode"),
)
kept()["submission_mode"] = submission_mode

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

months = pick_months()

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
    for record in terminations:
        selected = termination_picker(record, generate_003.termination_date(record))
        # Only carry codes the filer (or the death inference) actually chose;
        # build() does overrides.get(code, default), and a None would crash it.
        if selected is not None:
            status_overrides[record.employee_code] = selected

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
    blocking, soft = validate.validate(matched, month, period)
    blocking_total.extend(blocking)
    included = generate_003.included_for_month(matched, month)

    rows = []
    for record in included:
        gross, remuneration, uif_total = generate_003.employee_figures(record, month)
        emp = record.employee
        if generate_003.is_terminated_in_period(record, period):
            code = status_overrides.get(record.employee_code)
            status_label = (
                f"{code} — {EMPLOYMENT_STATUS_CODES[code]}" if code else "— not set"
            )
        else:
            status_label = f"01 — {EMPLOYMENT_STATUS_CODES['01']}"
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
                "Status (8280)": status_label,
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

# UI gate (not a validate.py blocking error): every declared termination needs a
# reason code before anything can be generated — a None override would crash
# build(), and a silent 06 costs an ex-employee their claim.
unset_terminations = [
    record.employee_code
    for record in terminations
    if record.employee_code not in status_overrides
]
if unset_terminations:
    st.error(
        "Select a reason (field 8280) for every employee who has left before "
        "files can be generated."
    )
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
_max_start = 1000 - len(ordered_months)
start_number = int(
    st.number_input(
        "Starting file number",
        min_value=1,
        max_value=_max_start,
        value=min(kept().get("start_sequence", 1), _max_start),
        step=1,
        key=mode_key("start_sequence"),
        help="Numbers run consecutively from here, one per selected month, "
             "in March-first order.",
    )
)
kept()["start_sequence"] = start_number

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
