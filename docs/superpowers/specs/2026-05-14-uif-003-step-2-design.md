# UIF 003 Generator — Step 2 Design: Parsers, Matcher, Validator, Generator + UI

Date: 2026-05-14
Status: pending spec review

## Goal

Take the two uploaded Sage CSVs (Year to Date Detail, Employee Details) plus a
small company-config form, and produce one or more downloadable SARS UIF
declaration files — one per selected month of the tax year — that reproduce
Sage's own output. This step completes the full pipeline: parse → match →
validate → generate → download.

## Reverse-engineering basis

The generation rules below were derived and cross-checked against two real Sage
sample sets:

- **2024 set**: `YearToDateDetail (2).csv`, `EmployeeDetail (1)2024.csv`,
  `20440843.003` (period 202402, 32 employees).
- **2025 set**: `YearToDateDetail (3).csv`, `20440843.004` (period 202502, 27
  employees in the file / 34 in the YTD), plus `UIFExportDetail 2025.pdf` (the
  human-readable equivalent of the `.004`).

Every formula below is confirmed exact against at least one sample; the byte-exact
regression tests (see Testing) pin them.

## Scope

In scope:
- `uif/models.py` — shared dataclasses
- `uif/parse_ytd.py` — Year to Date Detail parser
- `uif/parse_employees.py` — Employee Details parser
- `uif/match.py` — join the two on employee code
- `uif/validate.py` — blocking errors vs soft warnings
- `uif/generate_003.py` — build the declaration file bytes for one month
- `streamlit_app.py` — company-config form, month picker, preview, validation, download
- Anonymized test fixtures in `samples/` + unit/regression tests
- Rewrite of `FORMAT.md` to match these corrected rules

Out of scope (YAGNI):
- Persistence of any kind (stateless, per project constraints)
- In-app editing of parsed data
- Multi-company management
- A "catch-up sweep" mode (bundling unfiled prior-month finals into one file) —
  the app produces clean per-month files, which makes the sweep unnecessary
- Status codes beyond `01`/`06` until a real export needs them

## App flow

```
password → upload 2 CSVs → parse both → company-config form
→ pick month(s) → preview table + validation panel → generate → download
```

## Module breakdown

| Module | Responsibility | Key function |
|---|---|---|
| `uif/models.py` *(new)* | Dataclasses: `YtdRecord`, `EmployeeRecord`, `MatchedRecord`, `Company`, `MonthFigures` | — |
| `uif/parse_ytd.py` | YTD CSV → `{code: YtdRecord}` with per-month earning line items + UIF figures | `parse(file_bytes)` |
| `uif/parse_employees.py` | Employee Details CSV → `{code: EmployeeRecord}` | `parse(file_bytes)` |
| `uif/match.py` | Join on employee code → `list[MatchedRecord]` + mismatch warnings | `join(ytd, employees)` |
| `uif/generate_003.py` | Build one month's declaration file as bytes | `build(records, period, company)` |
| `uif/validate.py` | Per-month: split issues into blocking errors vs soft warnings | `validate(records, period)` |
| `streamlit_app.py` | UI wiring: form, month picker, preview, download | — |

### Data structures (`uif/models.py`)

- `Company`: `uif_ref`, `paye_ref`, `contact_name`, `contact_phone`,
  `contact_email_header`, `contact_email_footer`, `submission_mode`
  (`LIVE`/`TEST`), `file_extension` (default `003`)
- `MonthFigures`: `gross`, `remunerable`, `uif_total` — the three derived numbers
  for one employee in one month
- `YtdRecord`: `employee_code`, `employee_name` (raw, display only),
  `months: dict[str, dict[str, float]]` — month name → {earning line-item name →
  amount}. Keeps raw line items so `remunerable` can be computed.
- `EmployeeRecord`: `employee_code`, `surname`, `first_names`, `id_number`,
  `passport_number`, `date_of_birth`, `date_engaged`, `end_date`,
  `employee_status`, `uif_status`
- `MatchedRecord`: all `EmployeeRecord` fields + the YTD months data + provenance
  flags (`in_ytd`, `in_employees`)

## Parsing approach

Stdlib `csv` module, not pandas. Both files are block-structured reports
(variable column counts, label/value rows) — a row-by-row state machine fits far
better than a DataFrame. pandas is retained only for rendering the preview table.

**Encoding:** files are not UTF-8 — they use a `\xA0` (non-breaking space)
thousands separator. Decode UTF-8 with a cp1252 fallback. Number cleaning strips
`\xA0`, regular spaces, and commas before `float()`; empty cells → `0.0`.

### YTD parser

1. Locate the month-header row (cells include `March`, `April`, …). Build
   `{month_name: column_index}` from it — column positions are irregular
   (March=2, April=4, May=7, …, December=15, January=16, February=17) and MUST
   be read, never hardcoded. Confirmed identical layout across both YTD files.
2. Read the "Printed for period ending YYYY/MM/DD" line → the tax year.
3. A row whose first cell is `Employee code:` starts a new employee block; the
   second cell is the code. The next row holds `Status: …; From: …; [To: …]`.
4. Within a block, track the current section via section-header rows
   (`Earnings`, `Deductions`, `Company Contributions`, …).
5. Capture, per month column:
   - every line-item row in the `Earnings` section (name → amount) — needed for
     the remunerable calculation
   - the `Earnings` section's `TOTAL` row → `gross`
   - the `Unemployment insurance fund` rows in `Deductions` and in
     `Company Contributions` — kept for cross-checking only; `8320` is computed,
     not taken from these (see Generator)
6. Parse the `Status:` line: `Employed`/`New` vs `No longer employed`, and the
   `To:` date when present.

### Employee Details parser

1. A row whose first cell is `Employee code` starts a new employee block.
2. Within a block, extract fields by locating each known label and reading the
   value cell after it, bounded by the next known label on the same row. Value
   columns are inconsistent (col 1, 2, or 11 depending on the row) — a fixed
   value-column assumption does NOT work.
3. Field cleaning:
   - employee code: strip `.00` suffix → `"32"`
   - ID number: split on `.`, take the integer part, keep digits only, left-pad
     to 13 (handles the `.00` suffix and Excel's lost leading zero)
   - passport: verbatim, stripped (may contain letters and hyphens, e.g.
     `12-135849P-12`)
   - dates (`DD/MM/YYYY`) → `YYYYMMDD`

Note: employee codes are unique only within a single tax-year export. Across
years they can be reused/reassigned (the 2025 data has two different "George
Chinoda" records, codes 10 and 36). The app processes one matched YTD +
Employee Details pair at a time, so this is not a problem.

## Matcher

`join(ytd, employees)` joins on the normalized employee code. Returns
`(matched_records, warnings)` where `warnings` lists employees present in only
one CSV. In the 2024 reference data both CSVs hold a contiguous 1–32; the
mismatch path is still implemented.

## Generator — declaration file format

Confirmed against both `20440843.003` and `20440843.004`.

### Field-level rules

- **`8300`** (gross) = the `Earnings → TOTAL` value for the declared month.
- **`8310`** (UIF remuneration) = `min(remunerable, 17712.00)` where
  `remunerable = Σ (earning line-item amount × remunerable_pct(line-item name))`.
  `remunerable_pct`:
  - `"Travel allowance - 80%"` → `0.80`
  - `"Severance Pay"` → `0.00` (excluded from UIF remuneration — voluntary /
    loss-of-employment award)
  - every other earning type → `1.00`
  Verified: April-2025 Anthorn gross 7393.67, travel allowance 500 → remunerable
  7393.67 − 0.20×500 = 7293.67 = the file's `8310`. Shirley Surridge likewise
  (−210 = 0.20×1050).
- **`8320`** (UIF total) = `round(8310 × 0.01, 2) × 2` — round the 1% employee
  side, then double for employee + employer. Verified across both files (e.g.
  Bonde 2024: round(9933.52×0.01,2)=99.34, ×2=198.68 — matches the file, which a
  flat `8310×0.02` would not).
- **Number format:** format to 2 decimals, then strip a trailing `.00`
  (→ `11550`, but `6232.80` keeps its zero). Applies to `8300`, `8310`, `8320`,
  and footer sums `8130/8135/8140`.
- **`8200`** ID: digits only, 13 chars, leading zeros preserved, **unquoted**.
  **`8210`** passport: verbatim, **quoted**. Exactly one of the two per record;
  ID preferred when present.
- **`8280`** status: `Employed`/`New`/`Normal` → `01`; `No longer employed`/
  `Terminated` → `06`. Unquoted, zero-padded 2-digit.
- **`8270`** end date: present only for terminated employees; value = the `To:`
  date from the YTD status line, `YYYYMMDD`.
- **Dates** (`8250/8260/8270`): `YYYYMMDD`, unquoted.
- **Line endings:** `\r\n` on every line including the footer.
- **Encoding:** output encoded latin-1.

### Record layout

- Header `UICR`: `8000,8010,8015,8020,8030,8040,8050,8060,8070`
- Employee `UIWK`: `8001,8110,[8200|8210],8230,8240,8250,8260,[8270],8280,8300,8310,8320`
- Footer `UIEM`: `8002,8115,8120,8130,8135,8140,8150,8160`
  - `8130` = Σ `8300`, `8135` = Σ `8310`, `8140` = Σ `8320`, `8150` = record count

### Filename

`<UIF ref with leading zeros stripped>.<extension>` — e.g. `20440843.003`. The
extension is a config field (default `003`); the 2024 sample is `.003` and the
2025 sample is `.004`, suggesting an incrementing submission counter. **Open item
— confirm with user.** For a multi-month download, the zip contains
`<ref>_<YYYYMM>.<extension>` per file.

## Generation logic — strict per-month

For target month M, the file includes **every employee whose `Earnings → TOTAL`
for month M is greater than zero**, declared at month M's figures. Confirmed:

- **Feb 2025** — 27 of 34 YTD employees had February earnings → exactly those 27
  in the `.004`. The 7 absent are exactly the 7 with `No longer employed` status
  and R0 February earnings.
- **Feb 2024** — 31 of 32 had February earnings. The 32nd, Kwepile (terminated,
  R0 February), appears in the real `.003` at his *January* figure — a manual
  catch-up sweep, explicitly out of scope. The app's February 2024 output is
  therefore **31 records**; Kwepile's final declaration belongs in the January
  file, where strict-per-month places him automatically.

Terminated employees need no special inclusion handling: strict-per-month places
them in every month they were paid, and their last paid month becomes their
final declaration. They carry `8280=06` + `8270` in those records.

Edge cases: `Earnings TOTAL` ≤ 0 → employee skipped for that month. An employee
whose month-M earnings are entirely non-remunerable (e.g. only Severance Pay) →
included with `8310=0`, `8320=0`, plus a soft warning.

## Validator

`validate(records, period)` returns `(blocking_errors, soft_warnings)`:

- **Blocking** (no file generated): an employee with earnings in `period`
  missing *both* ID and passport; or missing DOB, start date, surname, or first
  name.
- **Soft warnings** (file still generates): employee present in only one CSV;
  employee whose UIF status is not contributing; an earning line-item type the
  remunerability map does not recognise (assumed 100% — verify); an employee
  with earnings but R0 UIF-remunerable.

## UI

- **Company-config form:** UIF ref, PAYE ref, filer name/phone, header email,
  footer email (defaults to header), submission mode (`LIVE`/`TEST`, default
  `LIVE`), file extension (default `003`). Entered each session; held in
  `st.session_state` so a multi-month run does not re-ask.
- **Month picker:** multiselect of the 12 tax-year months, derived from the YTD
  month-header row and "period ending" line, plus a select-all.
- **Preview:** per selected month, a table — name, ID/passport, gross (8300),
  remuneration (8310), UIF total (8320), status.
- **Validation panel:** blocking errors in red (download disabled); soft
  warnings in yellow (download still allowed).
- **Download:** one month → a single declaration file; multiple → a `.zip` of
  `<ref>_<YYYYMM>.<extension>` files.

## Testing & fixtures

- **Anonymized fixtures** committed to `samples/`: scrambled names, ID numbers,
  passports, addresses, and company name; real payroll amounts retained (amounts
  are not PII). Two sets:
  - 2024: anonymized YTD + Employee Details + expected `.003`
  - 2025: anonymized YTD + expected `.004` (Employee Details for 2025 not yet
    supplied — see Risks)
- **Regression tests** — byte-exact:
  - generate Feb 2025 from the 2025 fixtures → assert byte-equal to the
    anonymized `.004` (full 27-record reproduction)
  - generate Feb 2024 from the 2024 fixtures → assert byte-equal to the
    anonymized `.003` **with Kwepile removed and footer recomputed** (31 records;
    the corrected strict-per-month file). The raw 32-record sample is kept as a
    documented reference, not the test target.
  - generate Jan 2024 → assert Kwepile appears, at his January figures
- **Unit tests:** number formatting, ID cleaning, date conversion, the
  remunerable calculation (travel allowance + severance cases), `8320` rounding,
  both parsers.

## Risks / open items

- **File extension** (`.003` vs `.004`): assumed an incrementing submission
  counter, exposed as a config field. Needs user confirmation.
- **2025 Employee Details CSV** not yet supplied — without it the 2025
  regression test can verify all YTD-derived figures and the inclusion logic but
  must stub identity fields (ID/DOB/dates) from the `.004` itself. A real 2025
  Employee Details export would make it a full byte-exact test.
- **Remunerability map** is confirmed only for `Travel allowance - 80%` (80%)
  and `Severance Pay` (0%); all other earning types assumed 100%. The byte-exact
  tests catch any type that appears in a February sample and is wrong; types
  absent from both samples (e.g. `Leave paid out`, `Days worked`,
  `Back pay normal time`) remain unverified and trigger the soft warning.
- **Per-month status** is taken from the YTD's year-end snapshot, so a
  mid-year-terminated employee shows `8280=06` even in months before their
  actual end date. This reproduces both samples exactly; deriving status from
  start/end dates per month is a possible later refinement.
- **PDF period label**: `UIFExportDetail 2025.pdf` is headed "April 2025" but
  its figures match the `.004` (period 202502 = February 2025) and February
  YTD column exactly. Treated as a Sage label quirk, not a data issue.
