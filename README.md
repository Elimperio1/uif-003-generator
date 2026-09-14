# UIF-ektief

A Streamlit web app that converts two Sage CSV exports into one or more SARS
UIF declaration files (`.003` / `.004`), one per month, for the South African
tax year (March to February). Built for catching up on missed UIF filings when
Sage will only generate the current month.

The name is a pun on Afrikaans *effektief*: UIF, made effective.

## How it works

1. Upload the payroll file: the Sage **Year to Date Detail** CSV, or a
   **Standard Format** payroll workbook (.xlsx, one sheet per tax year —
   pick the tax year in the app).
2. Upload the employee master: the Sage **Employee Details** CSV, or the
   Standard Format master workbook (.xlsx, "Employee details" sheet).
   Formats are detected automatically, per file, and may be mixed.
   Sage CSV only: before uploading, open the Employee Details file in
   Excel, format column B as **Number** with 0 decimals, and save —
   otherwise Excel mangles SA ID numbers into scientific notation.
3. Fill the company / filer details once (UIF ref, PAYE ref, contact name,
   phone, email, submission mode).
4. Pick the month(s) you want declarations for.
5. Download the resulting declaration file (or a zip of files for a multi-month
   run) and upload to SARS uFiling.

### UI-19 PDF form

Switch **Output** to *UI-19 PDF form* to get the official UI-19 form filled in
instead (one PDF per month, 6 employees a page) to sign and send to the
Department of Employment and Labour. Same uploads; Step 2 asks for the form's
employer details (trading name and UIF ref required). This mode follows the
standalone UI19 script's rules, not the eDecs rules: leavers and starters in
the month are declared even if unpaid, and the UIF contributor Yes/No comes
from the UIF status. Columns H and J take the reasons picked in Step 4.

This mode also takes the **Sage report PDFs**, the standalone script's own
input: Year to Date Detail and Employee Details, **both** as PDFs (a PDF
can't be paired with a CSV: PDF employee codes keep their leading zeros, and
Sage can have distinct employees `026` and `0026`). An optional Company
Details PDF fills the empty employer fields. The eDecs file refuses PDFs: the
YTD PDF has only the earnings total, not the line items its remuneration
rules need.

No data is stored. Uploads are processed in memory and discarded when the browser
tab closes. No authentication: the app is intentionally public-facing.

## Local development

    pip install -r requirements.txt
    streamlit run streamlit_app.py

## Deploying to Streamlit Community Cloud

1. Push to the `main` branch of the public GitHub repo.
2. On https://share.streamlit.io, create a new app pointing at this repo and
   `streamlit_app.py`.
3. Deploy. No secrets needed.

## Project layout

    streamlit_app.py     entry point: upload UI, form, preview, download
    uif/                 parsing, joining, validation, generation
    tests/               unit + regression tests
    samples/             anonymised test CSVs (real ones in samples/private/, gitignored)
    FORMAT.md            SARS UIF declaration file format specification
    PROGRESS.md          build progress tracker

## Build status

See `PROGRESS.md` for current step.
