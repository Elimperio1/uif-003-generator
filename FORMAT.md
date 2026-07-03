# SARS UIF Electronic Declaration (eDecs) — File Format Specification

Source: UIF eDecs parsing handoff (2026-07-02), merged with observations
from a real accepted sample file. Where the two conflict, see
[Discrepancies vs. sample file](#discrepancies-vs-sample-file) — resolve
against a current accepted file in Step 3 before going live.

## File architecture

Three record types, in this order:

    [H]  8000 record — company profile header        (exactly one, first)
    [E]  8001 record — one row per employee          (repeats)
    [F]  8002 record — audit totals footer           (exactly one, last)

## File naming

`uuuuuuuu.nnn` — not `.csv` or `.txt`:

- `uuuuuuuu` — the 8-digit company UIF registration number, slash removed.
- `nnn` — sequential batch number per submission (`.001` first file,
  `.002` next, ...).

## Encoding & line endings

- ASCII / ISO-8859-1
- CRLF line terminators (`\r\n`)
- No trailing newline after the footer (verified against sample)
- **Rule C — no wrapping:** each record is exactly one line. Values must
  never be fragmented across lines (e.g. `354.24` split into `354.2` +
  `4` on the next row). Emit unwrapped plain text only.

Each record is a single line of comma-separated `<field_code>,<value>`
pairs. String values are double-quoted; numeric values are not.

## Header record (8000)

| Code | Description                                   | Example              |
|------|-----------------------------------------------|----------------------|
| 8000 | Record type identifier                        | `"UICR"` (or `"H"`)  |
| 8010 | UIF employer reference number, incl. slash    | `1234567/8`          |
| 8015 | Trading name                                  | `"Elimperio (Pty) Ltd"` |
| 8020 | PAYE number — 10 digits, starts with `7`      | `7930795960`         |
| 8030 | Company status                                | `"LIVE"`             |
| 8040 | Contact person (payroll admin name + surname) | `"Richard Coetzee"`  |
| 8050 | Contact number — 10-digit telephone           | `"0122590848"`       |
| 8060 | Email address (submission feedback alerts)    | `"tax@example.co.za"`|
| 8070 | Contribution period, CCYYMM — the timeline anchor for all row logic | `202607` |

## Employee record (8001)

One per employee in the payroll batch.

| Code | Description                                  | Required            | Example          |
|------|----------------------------------------------|---------------------|------------------|
| 8001 | Record type identifier                       | const               | `"UIWK"` (or `"E"`) |
| 8110 | UIF employer reference — matches 8010 exactly| yes                 | `1234567/8`      |
| 8200 | SA ID number — exactly 13 digits, unquoted   | one of 8200/8210    | `8306056177085`  |
| 8210 | Passport number — mandatory if 8200 blank    | one of 8200/8210    | `"BN487879"`     |
| 8220 | Employee personnel number (internal payroll code) | yes            | `"EMP014"`       |
| 8230 | Surname                                      | yes                 | `"Anthorn"`      |
| 8240 | First names                                  | yes                 | `"Sibonile"`     |
| 8250 | Date of birth, CCYYMMDD                      | yes                 | `19830605`       |
| 8260 | Date employed from, CCYYMMDD                 | yes                 | `20230824`       |
| 8270 | Date employed to (termination), CCYYMMDD     | see Rule A          | `20231231`       |
| 8280 | Employment status code (2 digits, below)     | yes                 | `01`             |
| 8290 | Reason code for non-contribution (1 digit)   | only if 8320 = 0.00 | `1`              |
| 8300 | Gross remuneration                           | yes                 | `11550.00`       |
| 8310 | Remuneration subject to assessment (capped)  | yes                 | `11550.00`       |
| 8320 | UIF contribution = 2% of 8310                | yes                 | `231.00`         |

### Employment status codes (field 8280)

| Code | Meaning                                      |
|------|----------------------------------------------|
| 01   | Active (contributing, working normally)      |
| 02   | Deceased                                     |
| 03   | Retired                                      |
| 04   | Dismissed                                    |
| 05   | Contract expired                             |
| 06   | Resigned                                     |
| 07   | Constructively dismissed                     |
| 08   | Employer's insolvency / liquidation          |
| 09   | Maternity / adoption leave (temporary suspension) |
| 10   | Illness leave / medically boarded            |
| 11   | Retrenched / staff reduction                 |
| 12   | Transfer to another corporate branch profile |
| 13   | Absconded / deserted duties                  |
| 14   | Business closed                              |
| 15   | Death of domestic employer                   |
| 16   | Voluntary severance package                  |
| 17   | Reduced working time                         |
| 18   | Commissioning parental leave                 |
| 19   | Parental leave                               |

### Non-contribution reason codes (field 8290)

| Code | Meaning                                                    |
|------|------------------------------------------------------------|
| 1    | Earned less than legal threshold                           |
| 2    | Registered Skills Act learnership contract                 |
| 3    | Independent contractor / non-natural corporate entity      |
| 4    | Long-term approved unpaid leave                            |
| 5    | Suspended without pay (pending disciplinary action)        |
| 6    | Maternity / illness / reduced time (maps to status 09, 10 or 17) |

## Footer record (8002)

Exactly one, last line. Must balance against the file body before the
output stream is sealed.

| Code | Description                                | Example          |
|------|--------------------------------------------|------------------|
| 8002 | Record type identifier                     | `"UIEM"` (or `"F"`) |
| 8115 | UIF employer reference (matches header)    | `1234567/8`      |
| 8120 | PAYE reference (10 digits, unquoted)       | `7930795960`     |
| 8130 | Sum of all 8300 values (gross)             | `298691.11`      |
| 8135 | Sum of all 8310 values (assessed)          | `249300.64`      |
| 8140 | Sum of all 8320 values (contributions due) | `4986.02`        |
| 8150 | Count of all 8001 (UIWK) rows              | `32`             |
| 8160 | Contact email (matches header 8060)        | `"tax@..."`      |

The handoff spec mandates the four totals (record count, sum 8300, sum
8310, sum 8320) but assigns no field codes; the codes above come from
the sample file.

## Validation rules (mandatory logic engine)

### Rule A — future termination constraint (critical)

Compare each employee's 8270 against the **last calendar day of the
month in 8070**. If 8270 is later:

- Force 8280 to `01` (Active).
- Emit 8270 completely blank.
- Calculate the normal 2% contribution as if fully active.

The termination status is withheld until the export month reaches the
actual exit month.

### Rule B — financial decimal rigidity

8300, 8310 and 8320 must always carry exactly 2 decimal places with `.`
separator (`17712.00`, never `17712`), uniformly across every row.

### Rule C — no buffer wrapping

See [Encoding & line endings](#encoding--line-endings): one record per
line, no value fragmentation.

### Rule D — zero-contribution dependency

- If 8320 is `0.00` (or blank): 8290 **must** hold a valid reason code
  (1–6).
- If 8320 > 0: 8290 **must** be entirely blank.

## Rules & caps

- **UIF remunerable cap:** R17,712.00 per month. If gross > 17712 then
  `8310` = `17712.00` regardless of gross.
- **UIF rate:** 2% total (1% employee + 1% employer). `8320` =
  `round(8310 * 0.02, 2)`. Field 8320 carries the *combined* amount.
- **Date format:** `CCYYMMDD`, no separators, unquoted.
- **Quoting:** string fields wrapped in `"`; numeric fields not.
- **Zero-contribution employees:** included in the file with 8290
  populated per Rule D — not silently omitted. (Supersedes the earlier
  "skip non-contributors" rule; see discrepancies below.)

## Source mapping (Sage CSVs → eDecs fields)

### Per-period (from Year to Date Detail CSV)

| Field | Source                                                           |
|-------|------------------------------------------------------------------|
| 8300  | "TOTAL" earnings row for the selected month                      |
| 8320  | "Unemployment insurance fund" deduction + same company contrib   |
| 8310  | derived: `8320 / 0.02` (trusts Sage's cap logic); `0.00` → Rule D |

### Per-employee identity (from Employee Details CSV)

| Field | Source                                                  |
|-------|---------------------------------------------------------|
| 8200  | "ID number" — strip non-digits, left-pad to 13          |
| 8210  | "Passport number" (use only if no SA ID)                |
| 8220  | "Employee code"                                         |
| 8230  | surname token from "Employee name" or "Full names"      |
| 8240  | "Full names"                                            |
| 8250  | "Date of birth" → CCYYMMDD                              |
| 8260  | "Date Engaged" → CCYYMMDD                               |
| 8270  | "End date" → CCYYMMDD if present, subject to Rule A     |
| 8280  | "Employee status": Normal → `01`, Resigned → `06`; other Sage statuses TBD against the 01–19 matrix |
| 8290  | derived per Rule D when the month's UIF is zero; default reason `1` (below threshold) unless Sage indicates otherwise |

### Per-file (one-time company config — captured from CSVs or input)

| Field          | Source                                       |
|----------------|----------------------------------------------|
| 8010/8110/8115 | UIF employer reference number                |
| 8015           | Trading name                                 |
| 8020/8120      | PAYE reference                               |
| 8040/8050      | Filer contact name and phone                 |
| 8060/8160      | Filer contact email                          |
| 8070           | User-selected period (CCYYMM)                |
| filename `nnn` | User-supplied sequential batch number        |

## Discrepancies vs. sample file

The handoff spec conflicts with the previously analysed accepted sample
in these places. Verify against a freshly accepted file during the
Step 3 diff test before trusting either side:

1. **Header codes 8010/8015/8020.** Sample: `8010="U1"` (format
   version), `8015="E03"` (file type), `8020="020440843"` (9-digit UIF
   ref). Handoff: 8010 = UIF ref with slash, 8015 = trading name,
   8020 = PAYE.
2. **UIF reference format.** Sample: 9 digits, no slash. Handoff:
   `1234567/8` (7 digits + slash + check digit; 8 digits total). The
   filename always uses the digits without the slash.
3. **Status code 09.** Sample-era spec: "Other". Handoff: "Maternity /
   adoption leave".
4. **Non-contributors.** Old rule: omit anyone whose Sage "UIF status"
   isn't `Contributes`. Handoff Rule D implies zero-contribution
   employees stay in the file with a 8290 reason code.
5. **Footer field codes.** Not specified in the handoff; taken from the
   sample.
