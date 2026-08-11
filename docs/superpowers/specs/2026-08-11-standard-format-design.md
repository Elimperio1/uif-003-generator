# UIF-ektief — Standard Format Input Support

Date: 2026-08-11
Status: pending spec review

## Goal

Accept a second input format — the "Standard Format" xlsx workbooks kept by
hand for clients not on Sage (first case: the client) — and
produce declaration files through the existing, unchanged pipeline. The two
current Sage CSV parsers and every generation rule in `generate_003.py` /
`FORMAT.md` stay exactly as they are; the new format only adds parsers that
emit the same `YtdRecord` / `EmployeeRecord` models.

## Reverse-engineering basis

Two real workbooks:

- **`List 2.xlsx`** — payroll workbook. One sheet per tax year (`2022`–`2027`),
  each containing the same 9 employee blocks: identity labels (`Employee Nr.:`,
  `Name:`, `Surname:`, `ID No.:`, `Income Tax Nr.:`, `Start date:`,
  `End date:`, `Reason:`) followed by a 12-row month table with earning columns
  `Salaris, Leave pay, Oortyd, Bonus, Reistoelaag, Verlof`, then
  `Bruto salaris, PAYE, SDL, UIF (1%), UIF (2%)`, then an unlabelled totals row.
- **`Copy of List.xlsx`** — master workbook. Sheet **"Employee details"** is a
  clean table: Employee Number, Name, Surname, ID No. / Passport Number,
  Date of Birth, Income Tax No., Start Date, End Date, Reason. Its `Sheet2`
  duplicates the current-year payroll block and is ignored.

### Confirmed data-quality rulings (user-approved)

1. **Tax year = sheet tab name; month = row position.** The in-sheet month
   labels and the "Financial year" header cell are stale template copies
   (sheets `2025`–`2027` all still read `03/2023..02/2024` / "2024", and
   different blocks in one sheet carry different stale years). Proof: sheet
   `2027`'s figures are identical to `Copy of List` Sheet2, which labels them
   `03/2026..02/2027`. The 1st table row is March, the 12th February; labels
   are ignored.
2. **Recompute UIF, warn on divergence.** Six month-rows across sheets
   `2025`/`2026` have a UIF column that is not 1% of gross (e.g. a month
   whose UIF column is well below 1% of gross; one row has UIF above 1% of
   gross). The app
   computes 8300/8310/8320 from the earning columns using the existing rules
   (R17,712 cap, ROUND_HALF_UP halves) and lists every divergent month as a
   soft warning so they can be eyeballed before download.

## Scope

In scope:
- `uif/parse_standard.py` *(new)* — both Standard Format parsers + format
  detection + year-sheet listing
- `uif/models.py` — add the Standard earning names to
  `CONFIRMED_FULL_REMUNERABLE` (no rule changes)
- `streamlit_app.py` — per-file format dispatch, tax-year selectbox for
  multi-year workbooks, workbook company-header hint
- `.gitignore` + file hygiene for the real workbooks (PII)
- Unit tests on synthetic workbooks; optional private-sample regression test
- `requirements.txt` — add `openpyxl`

Out of scope (YAGNI):
- Any change to Sage CSV parsing, matching, validation, or file generation
- Auto-filling the company form from the workbook header (the sheet's
  `UIF No.` cell is not the 9-digit uFiling reference)
- Editing/overriding parsed figures in-app
- A dedicated SARS status code for "Death" (no verified sample; stays `06`
  with a soft warning)
- Generic format-plugin registry (two formats, dispatch on one byte signature)

## Format detection & dispatch (per file)

Each of the two uploaders independently accepts `.csv` and `.xlsx` and is
dispatched on content, not extension or a global mode:

- `detect_format(bytes)` → `"standard"` if the bytes start with the zip magic
  `PK\x03\x04`, else `"sage"`.
- Payroll slot: `"sage"` → existing `parse_ytd.parse` (+
  `parse_ytd.tax_year_end_year`); `"standard"` →
  `parse_standard.parse_ytd(bytes, sheet_name)`.
- Employee slot: `"sage"` → existing `parse_employees.parse`; `"standard"` →
  `parse_standard.parse_employees(bytes)`.

Mixed pairings are explicitly supported (e.g. Sage Employee Details CSV +
Standard payroll workbook). The join key is unaffected: both sides pass
through `parse_employee_code`, so Sage's `32` and Standard's `001` normalise
consistently.

## `uif/parse_standard.py`

### `detect_format(file_bytes) -> str`

As above. Cheap, no openpyxl import needed.

### `list_year_sheets(file_bytes) -> list[str]`

Sheet names that are 4-digit years, sorted ascending. Used by the UI for the
tax-year picker and to decide whether a workbook is a payroll workbook at all.

### `parse_employees(file_bytes) -> dict[str, EmployeeRecord]`

Reads the **"Employee details"** sheet (exact name; error if absent). Header
row identifies columns by label; per data row with a non-empty Employee
Number:

| EmployeeRecord field | Source | Rule |
|---|---|---|
| `employee_code` | Employee Number | `parse_employee_code` (`001` → `1`) |
| `first_names` | Name | `extract_first_name` (leading token) |
| `surname` | Surname | column value verbatim, stripped — it is already a separate column, so "Van Der Walt" survives whole; no token-splitting |
| `id_number` / `passport_number` | ID No. / Passport Number | 13 digits after `parse_id_number` → `id_number`; anything else (e.g. `AB123456`) → `passport_number` verbatim |
| `date_of_birth`, `date_engaged`, `end_date` | Date of Birth / Start Date / End Date | DD/MM/YYYY → YYYYMMDD; `N/A`, `-`, blank → `""`. Cells may arrive as Excel datetimes — handle both |
| `employee_status` | End Date | `"Terminated"` if an end date parsed, else `"Normal"` |
| `uif_status` | — | `"Contributes"` (format has no UIF-status column) |

### `parse_ytd(file_bytes, sheet_name) -> tuple[dict[str, YtdRecord], list[str]]`

Reads one year sheet of the payroll workbook. Walks rows; `Employee Nr.:` in
column A starts a block. Within a block:

- Identity labels fill `status`/`end_date`: end date parsed from `End date:`
  (`N/A` → none) → `status = "Terminated"` else `"Employed"`.
  `Reason: Death` adds a soft warning that the declaration will carry status
  `06` like any other termination.
- The month table is the next 12 rows after the `Salaris …` header row whose
  column A matches `MM/YYYY` (blank spacer rows are skipped). The *i*-th such
  row (1-based) maps to `TAX_YEAR_MONTHS[i-1]` (March … February). The label's year/month
  digits are **ignored** (stale); fewer or more than 12 month rows in a block
  is a blocking parse error naming the employee.
- Earning line items: for each of `Salaris, Leave pay, Oortyd, Bonus,
  Reistoelaag, Verlof` with a nonzero value, add
  `earnings[month][column_name] = value`. Column positions are taken from the
  block's own header row, not hardcoded indices.
- Integrity soft warnings per month-row:
  - sheet `Bruto salaris` ≠ sum of the six earning columns (±0.01);
  - sheet `UIF 1%` ≠ recomputed 1% of capped remunerable (±0.02) — this is
    the user-approved divergence list. Cap months (sheet shows 177.12) are
    not divergent: the recomputation caps too.
- The unlabelled totals row and everything after `Sheet`-level junk is
  skipped; blocks with an empty Employee Nr. cell end the scan.

Returns the records **and** the collected soft warnings (the Sage parsers
return only records; the Standard parser has format-specific integrity checks
that belong to parsing, so its signature differs — the app forwards the
warnings into the existing `st.warning` stream).

### `tax_year_end_year(sheet_name) -> int`

`int(sheet_name)` — ruling 1.

## `uif/models.py` additions

Append to `CONFIRMED_FULL_REMUNERABLE`: `"Salaris"`, `"Leave pay"`,
`"Oortyd"`, `"Bonus"`, `"Verlof"`. **`Reistoelaag` is deliberately omitted**:
it is zero in all real data, and if it ever appears the existing "unknown
earning type — assumed 100% remunerable" soft warning fires so the 80%-vs-100%
call can be made on real figures. No existing entry, rate, cap, or status
mapping changes; `"Employed"`, `"Normal"`, `"Terminated"` are already in
`STATUS_CODE`.

## `streamlit_app.py` changes

- Both uploaders: `type=["csv", "xlsx"]`; copy updated to name both formats.
  The Excel column-B warning stays but is framed as Sage-CSV-only.
- After upload, dispatch each file per **Format detection** above.
- Standard payroll workbook with >1 year sheet → selectbox "Tax year ending
  February …" (options from `list_year_sheets`, default latest). One sheet →
  used directly. Zero year sheets → error. The resolved tax year is displayed
  exactly as it is for Sage today.
- Company header hint: when the payroll workbook is Standard, show the
  sheet's Company / PAYE No. / UIF No. cells as muted info text above the
  company form. Not auto-filled.
- Parse errors keep the existing `st.error` + `st.stop()` paths with
  plain-language messages.
- Everything from `match.join` onward is untouched.

## PII hygiene

`List 2.xlsx` and `Copy of List.xlsx` hold real names, SA IDs and pay. Add
`*.xlsx` to `.gitignore` and move both files to `samples/private/` (already
ignored) as `standard_payroll.xlsx` / `standard_master.xlsx`. They must never
be committed.

## Testing

- Unit tests build a small synthetic Standard workbook pair in-memory with
  openpyxl — including stale month labels, a UIF-divergent row, a Bruto
  mismatch row, a terminated employee (Death), a passport-style ID, and a
  13-digit ID — and assert: parsed models, warning texts, year-sheet listing,
  format detection, and that one generated month for the synthetic data passes
  through the existing `generate_003.build` with correct 8300/8310/8320.
- `tests/test_regression.py` pattern extended: an optional test that runs only
  when `samples/private/standard_*.xlsx` exist, asserting employee counts,
  the 2027-sheet figures match `Copy of List` Sheet2's independent copy, and
  the six known UIF divergences are reported.
- All existing tests must pass unchanged — that is the "output identical to
  before" guarantee for the Sage path.

## Dependencies

`requirements.txt`: add `openpyxl>=3.1`.
