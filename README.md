# UIF 003 Generator

A Streamlit web app that converts two Sage CSV exports into one or more
SARS UIF declaration files (`.003`) — one per month — for the South
African tax year (March–February). Built for catching up on missed UIF
filings when Sage only lets you submit the current month.

## How it works

1. Upload the **Year to Date Detail** CSV (payroll figures per month per
   employee).
2. Upload the **Employee Details** CSV (employee master with IDs,
   passports, DOBs, employment dates). Before uploading, open this file
   in Excel, format column B as **Number** with 0 decimals, and save —
   otherwise Excel mangles SA ID numbers into scientific notation.
3. Pick the month range you want declarations for.
4. Download the resulting `.003` file (or zip of files for a multi-month
   range) and upload to SARS uFiling.

No data is stored. CSVs are processed in memory and discarded at the end
of the session.

## Local development

    pip install -r requirements.txt
    cp .streamlit/secrets.toml.example .streamlit/secrets.toml
    # edit .streamlit/secrets.toml — set `password` to the shared password
    streamlit run streamlit_app.py

## Deploying to Streamlit Community Cloud

1. Push to the `main` branch of the public GitHub repo.
2. On https://share.streamlit.io, create a new app pointing at this repo
   and `streamlit_app.py`.
3. In the app's **Secrets** panel, add:

       password = "your-shared-password"

4. Deploy. Anyone with the URL who knows the password gets in.

## Project layout

    streamlit_app.py     entry point — auth gate, upload UI
    uif/                 parsing, joining, generation, validation
    tests/               unit + smoke tests
    samples/             anonymised test CSVs (real ones in samples/private/, gitignored)
    FORMAT.md            SARS UIF .003 file format specification
    PROGRESS.md          build progress tracker

## Build status

See `PROGRESS.md` for current step.
