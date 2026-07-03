"""
UIF 003 Generator — Streamlit app entry point.

Step 1 scope: scaffold only. The app gates access behind a shared password,
shows the upload instructions, and accepts the two CSV files. Parsing,
generation and download will land in step 2.
"""

import streamlit as st

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


st.title("UIF 003 Generator")

st.markdown(
    """
Generates SARS UIF eDecs declaration files (`uuuuuuuu.nnn`) for one or
more months of a South African tax year, using two CSV exports from Sage.

### What to upload

1. **Year to Date Detail** (the payroll CSV) — exported as-is from Sage.
2. **Employee Details** (the master CSV with ID/passport numbers) — **open
   this one in Excel first**, click on column B, set the cell format to
   **Number** with 0 decimals, then save. This forces SA ID numbers to
   export with full precision instead of being mangled into scientific
   notation.

Both CSVs must be for **the same company and the same tax year**. Drop
them below.
"""
)

st.divider()

col1, col2 = st.columns(2)

with col1:
    ytd_file = st.file_uploader(
        "Year to Date Detail CSV",
        type=["csv"],
        key="ytd_upload",
    )

with col2:
    emp_file = st.file_uploader(
        "Employee Details CSV",
        type=["csv"],
        key="emp_upload",
    )

st.divider()

if ytd_file and emp_file:
    st.success("Both files received. Generation logic lands in step 2.")
else:
    st.info("Upload both CSVs to continue.")
