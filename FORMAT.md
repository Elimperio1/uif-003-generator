# SARS UIF Declaration File (.003) — Format Specification

The UI-19 declaration is a flat text file with three record types: a
header (UICR), one or more employee records (UIWK), and a footer (UIEM).
The file is named `<UIFreferenceNumber>.003` and submitted to SARS via
uFiling.

## Encoding & line endings

- ASCII / ISO-8859-1
- CRLF line terminators (`\r\n`)
- No trailing newline after the footer (verified against sample)

Each record is a single line of comma-separated `<field_code>,<value>`
pairs. String values are double-quoted; numeric values are not.

## Header record (UICR)

Exactly one, first line.

| Code | Description                          | Type   | Example              |
|------|--------------------------------------|--------|----------------------|
| 8000 | Record identifier                    | const  | `"UICR"`             |
| 8010 | Format version                       | const  | `"U1"`               |
| 8015 | File type                            | const  | `"E03"`              |
| 8020 | UIF reference number (9 digits)      | string | `"020440843"`        |
| 8030 | Submission mode                      | const  | `"LIVE"` (or `"TEST"`)|
| 8040 | Filer contact name                   | string | `"Richard Coetzee"`  |
| 8050 | Filer contact phone                  | string | `"0122590848"`       |
| 8060 | Filer contact email                  | string | `"tax@example.co.za"`|
| 8070 | Period being declared (YYYYMM)       | int    | `202402`             |

## Employee record (UIWK)

One per contributing employee.

| Code | Description                              | Required | Example          |
|------|------------------------------------------|----------|------------------|
| 8001 | Record identifier                        | const    | `"UIWK"`         |
| 8110 | UIF reference (matches header 8020)      | yes      | `"020440843"`    |
| 8200 | SA ID number, 13 digits, unquoted        | one of   | `8306056177085`  |
| 8210 | Passport number, quoted                  | 8200/8210| `"BN487879"`     |
| 8230 | Surname                                  | yes      | `"Anthorn"`      |
| 8240 | First name                               | yes      | `"Sibonile"`     |
| 8250 | Date of birth (YYYYMMDD)                 | yes      | `19830605`       |
| 8260 | Employment start date (YYYYMMDD)         | yes      | `20230824`       |
| 8270 | Employment end date (YYYYMMDD)           | if term'd| `20231231`       |
| 8280 | Employee status code (see below)         | yes      | `01`             |
| 8300 | Gross earnings for the period            | yes      | `11550.00`       |
| 8310 | Remunerable earnings (capped at 17712)   | yes      | `11550.00`       |
| 8320 | UIF total = 2% of 8310                   | yes      | `231.00`         |

### Status codes (field 8280)

| Code | Meaning                                |
|------|----------------------------------------|
| 01   | Active / Normal                        |
| 02   | Deceased                               |
| 03   | Retired                                |
| 04   | Dismissed                              |
| 05   | Contract expired                       |
| 06   | Resigned                               |
| 07   | Constructive dismissal                 |
| 08   | Employer insolvent / liquidated        |
| 09   | Other                                  |

Codes `01` and `06` are confirmed seen in sample files; the rest are
from the SARS spec and not yet exercised against real data.

## Footer record (UIEM)

Exactly one, last line.

| Code | Description                              | Example          |
|------|------------------------------------------|------------------|
| 8002 | Record identifier                        | `"UIEM"`         |
| 8115 | UIF reference (matches header)           | `"020440843"`    |
| 8120 | PAYE reference (10 digits, unquoted)     | `7930795960`     |
| 8130 | Sum of all 8300 values                   | `298691.11`      |
| 8135 | Sum of all 8310 values                   | `249300.64`      |
| 8140 | Sum of all 8320 values                   | `4986.02`        |
| 8150 | Count of UIWK records                    | `32`             |
| 8160 | Contact email (matches header 8060)      | `"tax@..."`      |

## Rules & caps

- **UIF remunerable cap:** R17,712.00 per month. If gross > 17712 then
  `8310` = 17712.00 regardless of gross.
- **UIF rate:** 2% (1% employee + 1% employer combined). `8320` =
  `round(8310 * 0.02, 2)`.
- **Both contributions combined:** field 8320 carries the *total* UIF
  (employee + employer), not just one side.
- **Date format:** `YYYYMMDD`, no separators, unquoted.
- **Decimal format:** `.` separator, 2 decimal places for currency.
- **Quoting:** string fields wrapped in `"`; numeric fields not.
- **Skip non-contributors:** any employee whose Sage "UIF status" is not
  `Contributes` is omitted entirely from the file.

## Source mapping (Sage CSVs → .003 fields)

### Per-period (from Year to Date Detail CSV)

| .003 field | Source                                                           |
|------------|------------------------------------------------------------------|
| 8300       | "TOTAL" earnings row for the selected month                      |
| 8320       | "Unemployment insurance fund" deduction + same company contrib   |
| 8310       | derived: `8320 / 0.02` (trusts Sage's cap logic)                 |

### Per-employee identity (from Employee Details CSV)

| .003 field | Source                                                  |
|------------|---------------------------------------------------------|
| 8200       | "ID number" — strip non-digits, left-pad to 13          |
| 8210       | "Passport number" (use only if no SA ID)                |
| 8230       | surname token from "Employee name" or "Full names"      |
| 8240       | "Full names"                                            |
| 8250       | "Date of birth" → YYYYMMDD                              |
| 8260       | "Date Engaged" → YYYYMMDD                               |
| 8270       | "End date" → YYYYMMDD if present                        |
| 8280       | `01` if "Employee status" == "Normal", `06` if Resigned |

### Per-file (one-time company config — captured from CSVs or input)

| .003 field    | Source                                                  |
|---------------|---------------------------------------------------------|
| 8020/8110/8115| UIF reference number                                    |
| 8120          | PAYE reference                                          |
| 8040/8050     | Filer contact name and phone                            |
| 8060/8160     | Filer contact email                                     |
| 8070          | User-selected period (YYYYMM)                           |
