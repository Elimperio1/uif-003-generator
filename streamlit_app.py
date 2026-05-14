"""
UIF 003 Generator — Streamlit app entry point.

Gates access behind a shared password, takes the two Sage CSV exports plus a
company-config form, and produces one or more downloadable SARS UIF
declaration files — one per selected month of the tax year.
"""

import io
import zipfile

import pandas as pd
import streamlit as st

from uif import generate_003, match, parse_employees, parse_ytd, validate
from uif.models import TAX_YEAR_MONTHS, Company, period_code

st.set_page_config(
    page_title="UIF 003 Generator",
    page_icon="📄",
    layout="centered",
)


def _password_entered() -> None:
    if st.session_state.get("password", "") == st.secrets.get("password", ""):
        st.session_state["password_correct"] = True
        del st.session_state["password"]
    else:
        st.session_state["password_correct"] = False


def require_password() -> bool:
    """Return True only once the user has entered the correct shared password."""
    if st.session_state.get("password_correct"):
        return True

    st.title("UIF 003 Generator")
    st.text_input(
        "Password",
        type="password",
        on_change=_password_entered,
        key="password",
    )
    if st.session_state.get("password_correct") is False:
        st.error("Incorrect password.")
    return False


if not require_password():
    st.stop()


@st.cache_data(show_spinner=False)
def _parse_ytd(data: bytes):
    return parse_ytd.parse(data), parse_ytd.tax_year_end_year(data)


@st.cache_data(show_spinner=False)
def _parse_employees(data: bytes):
    return parse_employees.parse(data)


st.title("UIF 003 Generator")

st.markdown(
    """
Generates SARS UIF declaration files for one or more months of a South African
tax year, using two CSV exports from Sage.

### What to upload

1. **Year to Date Detail** (the payroll CSV) — exported as-is from Sage.
2. **Employee Details** (the master CSV with ID/passport numbers) — **open this
   one in Excel first**, click on column B, set the cell format to **Number**
   with 0 decimals, then save. This forces SA ID numbers to export with full
   precision instead of being mangled into scientific notation.

Both CSVs must be for **the same company and the same tax year**.
"""
)

st.divider()

col1, col2 = st.columns(2)
with col1:
    ytd_file = st.file_uploader("Year to Date Detail CSV", type=["csv"], key="ytd_upload")
with col2:
    emp_file = st.file_uploader("Employee Details CSV", type=["csv"], key="emp_upload")

st.divider()

if not (ytd_file and emp_file):
    st.info("Upload both CSVs to continue.")
    st.stop()

# --- Parse -----------------------------------------------------------------
try:
    ytd_data, tax_year_end = _parse_ytd(ytd_file.getvalue())
except Exception as exc:  # noqa: BLE001 - surface any parse failure to the user
    st.error(f"Could not parse the Year to Date Detail CSV: {exc}")
    st.stop()

try:
    emp_data = _parse_employees(emp_file.getvalue())
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not parse the Employee Details CSV: {exc}")
    st.stop()

matched, match_warnings = match.join(ytd_data, emp_data)

st.success(
    f"Parsed {len(ytd_data)} employees from the Year to Date Detail and "
    f"{len(emp_data)} from the Employee Details report. "
    f"Tax year ending February {tax_year_end}."
)
for warning in match_warnings:
    st.warning(warning)

# --- Company / filer details ----------------------------------------------
st.subheader("Company / filer details")
cfg_left, cfg_right = st.columns(2)
uif_ref = cfg_left.text_input("UIF reference number", key="uif_ref")
paye_ref = cfg_right.text_input("PAYE reference number", key="paye_ref")
contact_name = cfg_left.text_input("Filer contact name", key="contact_name")
contact_phone = cfg_right.text_input("Filer contact phone", key="contact_phone")
email_header = cfg_left.text_input("Contact email (file header)", key="email_header")
email_footer = cfg_right.text_input(
    "Contact email (file footer — defaults to header)", key="email_footer"
)
submission_mode = cfg_left.selectbox("Submission mode", ["LIVE", "TEST"], key="submission_mode")
file_extension = cfg_right.text_input("Output file extension", value="003", key="file_extension")

_required = {
    "UIF reference number": uif_ref,
    "PAYE reference number": paye_ref,
    "Filer contact name": contact_name,
    "Filer contact phone": contact_phone,
    "Contact email (file header)": email_header,
}
_missing = [name for name, value in _required.items() if not value.strip()]
if _missing:
    st.info("Fill in the company details to continue: " + ", ".join(_missing) + ".")
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

# --- Month selection -------------------------------------------------------
st.subheader("Months to generate")
months = st.multiselect(
    "Select the month(s) you need declaration files for",
    TAX_YEAR_MONTHS,
    key="months",
)
if not months:
    st.info("Select at least one month.")
    st.stop()

# --- Preview + validation --------------------------------------------------
st.subheader("Preview")
blocking_total: list[str] = []

for month in sorted(months, key=TAX_YEAR_MONTHS.index):
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
                "UIF total (8320)": uif_total,
                "Status": record.ytd.status,
            }
        )

    with st.expander(
        f"{month} ({period}) — {len(included)} employee(s)",
        expanded=(len(months) == 1),
    ):
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.write("No employees had earnings in this month.")
        for error in blocking:
            st.error(error)
        for warning in soft:
            st.warning(warning)

if blocking_total:
    st.error("Resolve the blocking errors above before files can be generated.")
    st.stop()

# --- Generate + download ---------------------------------------------------
st.subheader("Download")
ref_for_name = company.uif_ref.lstrip("0") or company.uif_ref
ordered_months = sorted(months, key=TAX_YEAR_MONTHS.index)

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
        f"Download {filename}",
        data=content,
        file_name=filename,
        mime="text/plain",
    )
else:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename, content in files.items():
            archive.writestr(filename, content)
    st.download_button(
        f"Download {len(files)} declaration files (.zip)",
        data=zip_buffer.getvalue(),
        file_name=f"{ref_for_name}_uif_declarations.zip",
        mime="application/zip",
    )
