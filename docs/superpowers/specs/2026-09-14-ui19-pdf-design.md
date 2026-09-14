# UI-19 PDF form output — design

_2026-09-14 · branch `ui19-pdf` · approved in chat by Melton_

## Goal

A second output mode. The app keeps producing the eDecs `.NNN` file exactly as
today; a toggle switches it to producing the official **UI-19 PDF form**
instead — the form the standalone script `C:\Projects\UI19_Automation_7`
fills. One output per run.

**Governing rule:** each mode follows its own rules. The eDecs path is
byte-for-byte unchanged. The UI-19 path follows the standalone script's rules
(`sage_reader.employees_from_ytd_detail`, `pdf_writer.py`, `ui19_import.py`),
applied to the data the app already parses. Deviations are listed explicitly
below; there are no others.

## Scope

In: mode toggle; UI-19 row builder (script rules); the script's PDF writer,
layout and official PDF; the parser additions those rules need; UI-19
employer fields; H/J code pickers; UI-19 warnings; PDF/zip download.

Out: Sage **PDF** input, Company Details PDF auto-fill, the xlsx working copy,
reconciliation between the two outputs, retiring the standalone script.

## Architecture

| Unit | Purpose |
|---|---|
| `uif/ui19.py` | Script rules → form rows + warnings. Pure; no Streamlit, no PDF. |
| `uif/ui19_pdf.py` | Port of `pdf_writer.py`; returns PDF `bytes`. |
| `uif/assets/UI19_official.pdf`, `uif/assets/ui19_layout.json` | Copied verbatim from the script (`pdf_layout.json` renamed). |
| `uif/models.py` | New defaulted fields (below). |
| `uif/parse_ytd.py`, `parse_employees.py`, `parse_standard.py` | Read the extra data. |
| `streamlit_app.py` | Toggle, mode-specific Step 2 / Step 4 / Step 5. |

`requirements.txt` gains `reportlab>=4.4,<6` and `pypdf>=6,<7` (both
pure-Python wheels, confirmed available for Python 3.14).

### Model additions (all defaulted — eDecs output unaffected)

- `YtdRecord.start_date: str = ""` — "From:" on the Sage status line (YYYYMMDD).
- `YtdRecord.uif_deducted: dict[str, float]` — employee UIF deduction per month;
  **empty when the report has no UIF line** (script's `uif_amt is None`).
  Sage: first Deductions row starting "Unemployment insurance fund".
  Standard: the first `UIF` column.
- `EmployeeRecord.employee_name: str = ""` — raw Sage "Employee name"
  (`Title Initials Surname`).
- `EmployeeRecord.full_names: str = ""` — raw full first names (Sage
  "Full names", Standard "Name").
- `EmployeeRecord.average_hours: float | None = None` — Sage
  "Average working hours per period"; comma decimal accepted.
- `EmployeeRecord.uif_status_reported: bool = True` — `False` for Standard
  Format, whose `uif_status="Contributes"` is an assumed default, not report data.

## UI-19 rules (`uif/ui19.py`)

Iterate YTD records **in report order**; look up the employee record by code.
For declared month `M` of calendar year `Y` (from `period_code`):

1. **Name.** Employee record with `employee_name` → script
   `split_employee_detail_name` (title, run of ≤3-char uppercase initials,
   rest = surname; initials formatted `J.P.`). Employee record without it
   (Standard) → `surname` + script `initials_from_first_names(full_names)`.
   No record, or empty surname → script `split_full_name(ytd.employee_name)`.
   Empty surname after that → skip the row.
2. **Dates.** Start = employee `date_engaged` else YTD `start_date`;
   end = employee `end_date` else YTD `end_date` (employee record wins —
   opposite of eDecs). Printed whenever known, DDMMYY.
3. **Inclusion.** `gross ≠ 0` **or** UIF deducted ≠ 0 **or** start in M/Y
   **or** end in M/Y.
4. **Gross.** `ytd.gross(M)`, uncapped; printed Rand / cents split
   (script `_fmt_money`).
5. **ID.** `id_number` else `passport_number` else blank.
6. **Hours.** `average_hours`, else blank.
7. **UIF contributor.** If `uif_status_reported` and status text present:
   contains "does not" or "exempt", or equals "no" → `NO`; contains
   "contribut" → `YES`. Otherwise UIF deduction for M known → `YES` if > 0
   else `NO`. Otherwise blank + warning.
8. **H — termination reason.** *Deviation (approved):* prefilled from the
   Step 4 pick, leading zero dropped (`06` → `6`). A row gets a picker when
   its end date's YYYYMM ≤ the declared period. Pickers reuse the eDecs
   widget keys (`status_8280_<code>`) so picks survive a mode switch; the
   "Reason: Death" → `02` preselection carries over.
9. **J — non-contribution reason.** *Deviation (approved):* a picker for
   every `NO` row, options `1`–`9` from the form's own table; preselected
   `6` when gross is 0, otherwise empty. Blank for `YES` / unknown.
10. **Warnings (script's, per month):** employees not found in Employee
    Details; missing ID/passport; contributor undetermined; hours missing
    only when there is no Employee Details data at all (so never in the app,
    which requires that upload — the script's own condition). *Addition (approved):* ID/passport
    longer than the 13 form boxes (the writer truncates it).
11. **Name titles.** *Deviation:* `mt` added to the script's title list —
    the app already fixed "Mt N Langeni" for eDecs; the script would print
    surname "Mt N Langeni".

## PDF (`uif/ui19_pdf.py`)

`pdf_writer.py` unchanged in behaviour: 6 rows per page (layout JSON),
employer block repeated, "(Page X of Y)" when > 1 page, month label in the
form's month box, UIF ref printed as typed and allowed to overflow its boxes,
declaration date = today `DD/MM/YYYY`, signature blank. Only change:
`write_pdf(...) -> bytes` instead of writing a path; base PDF read once.

Month label `"<Month> <YYYY>"`. Filename `UI19_<Month>_<YYYY>.pdf`; several
months → `UI19_<first>_to_<last>.zip`.

## UI flow

Toggle under the header: **eDecs file (.NNN)** | **UI-19 PDF form**
(`key="output_mode"`). Steps 1 and 3 unchanged.

- **Step 2, UI-19:** UIF reference (required), trading name (required), PAYE,
  CIPRO no., branch no., physical / work / postal address, email, phone, fax,
  authorised person, declaration name, declaration ID number. Shared keys
  with eDecs (`uif_ref`, `paye_ref`, `contact_name` → authorised person,
  `contact_phone`, `email_header`) so values persist across a switch. No
  eDecs company validation in this mode.
- **Step 4, UI-19:** H pickers, J pickers, per-month preview table
  (surname, initials, ID, gross, hours, start, end, H, UIF, J) and UI-19
  warnings. No eDecs `validate` in this mode.
- **Gate:** every H and J picker set before Step 5.
- **Step 5, UI-19:** no file-number input; PDF or zip download.

## Testing

- Unit tests per rule in `tests/test_ui19.py` (names, inclusion incl.
  unpaid leaver, dates precedence, contributor incl. Standard fallback,
  H/J mapping, warnings, report order).
- Parser tests for each new field (Sage YTD UIF line + From date, Employee
  Details raw name / full names / hours, Standard UIF column + flag).
- `tests/test_ui19_pdf.py`: 7 rows → 2 pages; overlay text located inside the
  surname column bounds and month box.
- Existing suite (151 passed, 2 skipped) and the private Standard Format
  regression unchanged.
- **Open verification:** no Sage CSV sample is on disk, so the
  "Unemployment insurance fund" row label and the hours value format are
  from the script's PDF reading. Confirm on a real Sage CSV at smoke test.
- Smoke test by Melton on a real month before merge. Branch not pushed or
  merged until then.
