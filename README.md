# UIF-ektief

A Streamlit web app that converts two Sage CSV exports into one or more SARS
UIF declaration files (`.003` / `.004`), one per month, for the South African
tax year (March to February). Built for catching up on missed UIF filings when
Sage will only generate the current month.

The name is a pun on Afrikaans *effektief*: UIF, made effective.

## How it works

1. Upload the **Year to Date Detail** CSV (payroll figures per month per
   employee).
2. Upload the **Employee Details** CSV (employee master with IDs, passports,
   DOBs, employment dates). Before uploading, open this file in Excel, format
   column B as **Number** with 0 decimals, and save. Otherwise Excel mangles SA
   ID numbers into scientific notation.
3. Fill the company / filer details once (UIF ref, PAYE ref, contact name,
   phone, email, submission mode).
4. Pick the month(s) you want declarations for.
5. Download the resulting declaration file (or a zip of files for a multi-month
   run) and upload to SARS uFiling.

No data is stored. CSVs are processed in memory and discarded when the browser
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
