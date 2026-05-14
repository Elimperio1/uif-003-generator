# UIF 003 Generator — Step 2 Design: Parsers, Matcher, Validator, Generator + UI

Date: 2026-05-14
Status: approved (design), pending spec review

## Goal

Take the two uploaded Sage CSVs (Year to Date Detail, Employee Details) and a
small company-config form, and produce one or more downloadable SARS UIF `.003`
declaration files — one per selected month of the tax year. This step completes
the full pipeline: parse → match → validate → generate → download.

## Scope

In scope:
- `uif/models.py` — shared dataclasses
- `uif/parse_ytd.py` — Year to Date Detail parser
- `uif/parse_employees.py` — Employee Details parser
- `uif/match.py` — join the two on employee code
- `uif/validate.py` — blocking errors vs soft warnings
- `uif/generate_003.py` — build `.003` bytes for one month
- `streamlit_app.py` — company-config form, month picker, preview, validation, download
- Anonymized test fixtures in `samples/` + unit/regression tests
- Rewrite of `FORMAT.md` to correct two wrong rules

Out of scope (YAGNI):
- Persistence of any kind (stateless, per the project constraints)
- In-app editing of parsed data
- Multi-company management
- "Consolidated catch-up" generation mode (strict per-month only)
- Status codes beyond `01`/`06` until a real export needs them

## App flow

```
password → upload 2 CSVs → parse both → company-config form
→ pick month(s) → preview table + validation panel → generate → download
```

## Module breakdown

| Module | Responsibility | Key function |
|---|---|---|
| `uif/models.py` *(new)* | Dataclasses: `YtdRecord`, `EmployeeRecord`, `MatchedRecord`, `Company` | — |
| `uif/parse_ytd.py` | YTD CSV → `{code: YtdRecord}` with per-month gross + UIF dedn + UIF contrib | `parse(file_bytes)` |
| `uif/parse_employees.py` | Employee Details CSV → `{code: EmployeeRecord}` | `parse(file_bytes)` |
| `uif/match.py` | Join on employee code → `list[MatchedRecord]` + mismatch warnings | `join(ytd, employees)` |
| `uif/validate.py` | Per-month: split issues into blocking errors vs soft warnings | `validate(records, period)` |
| `uif/generate_003.py` | Build one month's `.003` as bytes | `build(records, period, company)` |
| `streamlit_app.py` | UI wiring: form, month picker, preview, download | — |

### Data structures (`uif/models.py`)

- `Company`: `uif_ref`, `paye_ref`, `contact_name`, `contact_phone`, `contact_email`, `submission_mode` (`LIVE`/`TEST`)
- `YtdRecord`: `employee_code`, `employee_name` (raw, for display), `months: dict[str, MonthFigures]`
  where `MonthFigures` = `gross`, `uif_deduction`, `uif_contribution`
- `EmployeeRecord`: `employee_code`, `surname`, `first_names`, `id_number`, `passport_number`,
  `date_of_birth`, `date_engaged`, `end_date`, `employee_status`, `uif_status`
- `MatchedRecord`: all `EmployeeRecord` fields + the 12-month figures + provenance flags
  (`in_ytd`, `in_employees`)

## Parsing approach

Stdlib `csv` module, not pandas. Both files are block-structured reports (variable
column counts, label/value rows) — a row-by-row state machine fits far better than
a DataFrame. pandas is retained only for rendering the preview table in Streamlit.

**Encoding:** files are not UTF-8 — they use a `\xA0` (non-breaking space) thousands
separator. Decode UTF-8 with a cp1252 fallback. Number cleaning strips `\xA0`,
regular spaces, and commas before `float()`; empty cells → `0.0`.

### YTD parser

1. Locate the month-header row (the row whose cells include `March`, `April`, …).
   Build `{month_name: column_index}` from it — column positions are irregular
   (March=2, April=4, May=7, …) so this MUST be read, never hardcoded.
2. Iterate rows. A row whose first cell is `Employee code:` starts a new employee
   block; the second cell is the code.
3. Within a block, track the current section via section-header rows
   (`Earnings`, `Deductions`, `Company Contributions`, …).
4. Capture:
   - the `TOTAL` row while in the `Earnings` section → `gross` per month
   - the `Unemployment insurance fund` row while in `Deductions` → `uif_deduction` per month
   - the `Unemployment insurance fund` row while in `Company Contributions` → `uif_contribution` per month

### Employee Details parser

1. A row whose first cell is `Employee code` starts a new employee block.
2. Within a block, extract fields by locating each known label and reading the
   value cell after it, bounded by the next known label on the same row. (Value
   columns are inconsistent — col 1, col 2, or col 11 depending on the row — so a
   fixed value-column assumption does NOT work.)
3. Field cleaning:
   - employee code: strip `.00` suffix → `"32"`
   - ID number: split on `.`, take integer part, keep digits only, left-pad to 13
     (handles the `.00` suffix and Excel's lost leading zero)
   - passport: verbatim, stripped
   - dates (`DD/MM/YYYY`) → `YYYYMMDD`
   - employee status: `Normal`/`Terminated` retained for the generator's mapping

## Matcher

`join(ytd, employees)` joins on the normalized employee code. Returns
`(matched_records, warnings)` where `warnings` lists employees present in only
one CSV. In the reference data both CSVs hold a contiguous 1–32, so the join is
complete — but the mismatch path is still implemented.

## Validator

`validate(records, period)` returns `(blocking_errors, soft_warnings)` for a
given month:

- **Blocking** (no file generated at all): an employee with earnings in `period`
  who is missing both ID and passport; missing DOB, start date, surname, or
  first name.
- **Soft warnings** (file still generates): employee present in only one CSV; an
  employee whose UIF status is not `Contributes` (excluded from the file).

## Generator — `.003` format rules

Verified against the real sample `20440843.003`. These correct two errors in the
original `FORMAT.md`, which will be rewritten.

- **`8300`** = YTD `Earnings → TOTAL` for the month (gross, verbatim)
- **`8310`** = `min(8300, 17712.00)` — hard cap (NOT "derived from 8320")
- **`8320`** = YTD UIF *deduction* + YTD UIF *company contribution* for the month,
  summed straight from Sage (NOT recomputed as 2% of 8310 — preserves Sage's
  per-side rounding; e.g. Bonde = 99.34 + 99.34 = 198.68, not 198.67)
- **Number format:** `%.2f`, then strip a trailing `.00` (→ `11550`, but `6232.80`
  keeps its zero)
- **`8200`** ID: digits only, padded to 13, **unquoted**, leading zeros preserved
- **`8210`** passport: verbatim, **quoted**. Exactly one of `8200`/`8210` per record.
- **`8280`** status: `Normal`→`01`, `Terminated`→`06`. Unquoted, zero-padded.
- **`8270`** end date: present only for terminated employees.
- **Dates:** `YYYYMMDD`, unquoted.
- **Line endings:** `\r\n` on every line including the footer.
- **Encoding:** output encoded latin-1.
- **Filename:** `<UIFref with leading zeros stripped>.003` (e.g. `20440843.003`).

Record layout:
- Header `UICR`: `8000,8010,8015,8020,8030,8040,8050,8060,8070`
- Employee `UIWK`: `8001,8110,[8200|8210],8230,8240,8250,8260,[8270],8280,8300,8310,8320`
- Footer `UIEM`: `8002,8115,8120,8130,8135,8140,8150,8160`

## Strict per-month logic

For month M's file, include an employee **iff**:
1. their UIF status is `Contributes`, AND
2. their gross for month M is greater than 0.

All figures come from month M's column only. Consequence: an employee who stopped
earning mid-year (e.g. Kwepile — R0 in February) appears in their last earning
month's file, not later ones. This means the generated February file will NOT
byte-match the supplied sample `20440843.003` (which included Kwepile's January
figure under the February period and had 32 records); the corrected strict
February file has 31 records and recomputed footer totals.

Edge cases: zero/negative month → employee skipped for that month; terminated
employees are included normally if they have earnings that month; missing both
ID and passport → blocks the whole file.

## UI

- **Company-config form:** UIF ref, PAYE ref, filer name/phone/email, submission
  mode (`LIVE`/`TEST`, default `LIVE`). Entered each session; held in
  `st.session_state` so a multi-month run does not re-ask.
- **Month picker:** multiselect of the 12 tax-year months, derived from the YTD
  month-header row and the "Printed for period ending" line, plus a select-all.
- **Preview:** per selected month, a table — name, ID/passport, gross, capped
  (8310), UIF total (8320), status.
- **Validation panel:** blocking errors in red (download disabled); soft warnings
  in yellow (download still allowed).
- **Download:** one month → a single `.003`; multiple → a `.zip` containing
  `<ref>_<YYYYMM>.003` per month.

## Testing & fixtures

- **Anonymized fixtures** committed to `samples/`: scrambled names, ID numbers,
  passports, addresses, and company name; real payroll amounts retained (amounts
  are not PII). Derived from the user's real exports.
- **`samples/expected_202402.003`** — the *corrected strict-February* file: derived
  from the real sample by removing zero-February employees (Kwepile) and
  recomputing the footer sums and count. This is the byte-exact regression target.
  While building it, all 32 records are verified against the YTD; any record
  besides Kwepile that deviates from its February column is flagged.
- **Unit tests:** number formatting, ID cleaning, date conversion, YTD parser,
  Employee Details parser.
- **Regression test:** generate the February file from the anonymized fixtures +
  anonymized company config; assert byte-exact equality with
  `samples/expected_202402.003`. Plus a check that Kwepile correctly appears in
  the January output.

## Risks / open items

- Status-code mapping covers only `Normal` and `Terminated` (the only values in
  the reference export). Other Sage status values will need mapping when a real
  export contains them; until then they are surfaced as a soft warning rather
  than silently mis-coded.
- The supplied sample `.003`'s employee ordering is neither code-order nor
  alphabetical; the generator emits in employee-code order (deterministic). The
  regression fixture is built in the same order, so ordering is not a test
  concern.
