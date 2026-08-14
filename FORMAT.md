# SARS UIF Declaration File — Format Specification

The UIF declaration is a flat text file with three record types: a header
(`UICR`), one or more employee records (`UIWK`), and a footer (`UIEM`). It is
submitted to SARS via uFiling.

This spec is verified against two real Sage exports:
`20440843.003` (period 202402) and `20440843.004` (period 202502).

## Encoding & line endings

- **ASCII**, as required by spec §5 ("The file must be submitted in ASCII
  format"). Accented characters are transliterated rather than replaced, so
  `Böhme` is written `Bohme`, not `B?hme`. See `generate_003.to_ascii`.
- CRLF (`\r\n`) line terminators on **every** line, including the footer
  (the file ends with a trailing `\r\n`)

Each record is a single line of comma-separated `<field_code>,<value>` pairs.
String values are double-quoted; numeric values are not.

## Filename

`uuuuuuuu.nnn` (spec §12), where `uuuuuuuu` is the **last 8 digits** of field
`8020` — digits only, the slash excluded — and `nnn` is a 3-digit file number.
So `1234567/8` gives `12345678`, and `020440843` gives `20440843`.

Note this is "last 8 digits", not "strip leading zeros": the two rules agree
only for a reference shaped `0` + 8 digits, which is why the real sample
`020440843` did not expose the difference. `000123456` is `00123456`, not
`123456`.

The file number is **set by the filer**, not derived from the batch. Numbers
run consecutively from the chosen start, one per selected month, in
March-first order. This matters because §12/§13 say a repeated filename means
"the last file received will be used, and it will overwrite all previously
sent files with the same file name" — so a correction batch that restarted at
`.001` would silently destroy the original submission at the Fund. The earlier
`.003` / `.004` Sage exports were the third and fourth submissions of such a
sequence.

## Number format

Currency values are formatted to 2 decimal places, then a trailing `.00` is
stripped — so `11550.00` is written `11550`, but `6232.80` keeps its `.80`.
Applies to `8300`, `8310`, `8320` and the footer sums `8130/8135/8140`.

## Header record (UICR)

Exactly one, first line.

| Code | Description                          | Type   | Example                  |
|------|--------------------------------------|--------|--------------------------|
| 8000 | Record identifier                    | const  | `"UICR"`                 |
| 8010 | Format version                       | const  | `"U1"`                   |
| 8015 | File type                            | const  | `"E03"`                  |
| 8020 | UIF reference number                 | string | `"020440843"`            |
| 8030 | Submission mode                      | string | `"LIVE"` (or `"TEST"`)   |
| 8040 | Filer contact name                   | string | `"Richard Coetzee"`      |
| 8050 | Filer contact phone                  | string | `"0122590848"`           |
| 8060 | Filer contact email                  | string | `"tax@elimperio.co.za"`  |
| 8070 | Period being declared (YYYYMM)       | int    | `202402`                 |

`8020` is normalised before it is written: non-numeric characters stripped and
zero-filled from the left to 9 digits, per spec §8 ("123456/8 should be sent as
001234568"). An invalid `8020` rejects the **entire file**, so the app also
runs the Appendix A check digit — but only as a warning, and only for
references with a 6-digit base. Appendix A publishes multipliers for that
length alone, and real 7-digit-base references such as `2044084/3` do not
validate under any straightforward extension of it. Treating those as invalid
would block good submissions, so they are left unchecked.

`8040`, `8050`, `8060` and `8160` are cut to their declared lengths (30, 16,
50, 50) — see `models.FIELD_LENGTHS`.

## Employee record (UIWK)

One per included employee. Field order:
`8001, 8110, [8200|8210|8220], 8230, 8240, 8250, 8260, [8270], 8280, [8290],
8300, 8310, 8320`

| Code | Description                              | Required  | Example          |
|------|------------------------------------------|-----------|------------------|
| 8001 | Record identifier                        | const     | `"UIWK"`         |
| 8110 | UIF reference (matches header 8020)      | yes       | `"020440843"`    |
| 8200 | SA ID number, 13 digits, **unquoted**    | one of    | `8306056177085`  |
| 8210 | Passport number, **quoted**, ≤16         | 8200/     | `"BN487879"`     |
| 8220 | Payroll number, **quoted**, ≤25          | 8210/8220 | `"0042"`         |
| 8230 | Surname (≤120)                           | yes       | `"Anthorn"`      |
| 8240 | First names (≤90)                        | yes       | `"Sibonile"`     |
| 8250 | Date of birth (YYYYMMDD)                 | yes       | `19830605`       |
| 8260 | Employment start date (YYYYMMDD)         | yes       | `20230824`       |
| 8270 | Employment end date (YYYYMMDD)           | if term'd | `20231231`       |
| 8280 | Employee status code                     | yes       | `01`             |
| 8290 | Reason for non-contribution              | if 8320=0 | `06`             |
| 8300 | Gross earnings for the period            | yes       | `11550`          |
| 8310 | UIF remuneration (see below)             | yes       | `11550`          |
| 8320 | UIF total (see below)                    | yes       | `231`            |

`8200` is preferred when present, then `8210`, then `8220`. ID numbers preserve
leading zeros and are unquoted. Passports are quoted verbatim (they may contain
letters and hyphens, e.g. `"12-135849P-12"`).

`8220` carries "the personnel, clock card or payroll number" (spec §8) and is
filled from the employee code. Its presence is what stops a record with no ID
and no passport being rejected — §9 rejects only when all three are absent —
so the app warns about a missing ID instead of refusing to build the file.

### Status codes (field 8280)

The full spec §8 list is in `models.EMPLOYMENT_STATUS_CODES` (01 Active,
02 Deceased, 04 Dismissed, 05 Contract Expired, 06 Resigned, 11 Retrenched,
14 Business Closed, and so on).

The payroll export only distinguishes "employed" from "no longer employed", so
it can supply `01` and nothing more specific than `06`. Because `06` is a valid
code, SARS accepts it silently — and since resignation generally disqualifies
a UIF claim, a wrong `06` costs the employee their benefit with no error
anywhere. The app therefore lists every termination in Step 4 and lets the
filer set the real code per employee; `06` is pre-selected only because it
preserves the previously verified output.

`8270` is written whenever a termination is being declared, **except** for
codes `01`, `09` and `10` — spec §9 warns when an end date accompanies a status
that means the employee is still employed.

### Reason for non-contribution (field 8290)

Required whenever `8320` is zero (spec §8), otherwise SARS warns on `8290`,
`8300`, `8310` and `8320` at once. The app emits `06` ("no income paid for the
payroll period"), the only code that fits the reachable case — an employee paid
solely a non-remunerable amount such as severance.

## Footer record (UIEM)

Exactly one, last line.

| Code | Description                              | Example          |
|------|------------------------------------------|------------------|
| 8002 | Record identifier                        | `"UIEM"`         |
| 8115 | UIF reference (matches header)           | `"020440843"`    |
| 8120 | PAYE reference (unquoted)                | `7930795960`     |
| 8130 | Sum of all 8300 values                   | `298691.11`      |
| 8135 | Sum of all 8310 values                   | `249300.64`      |
| 8140 | Sum of all 8320 values                   | `4986.02`        |
| 8150 | Count of UIWK records (unquoted)         | `32`             |
| 8160 | Contact email (footer)                   | `"tax@..."`      |

`8060` (header email) and `8160` (footer email) can legitimately differ; the
app collects both, defaulting the footer to the header value.

## Calculation rules

All three derived numbers come from the **Year to Date Detail** report.

### 8300 — Gross earnings

The `Earnings → TOTAL` row value for the declared month.

### 8310 — UIF remuneration

`min(remunerable, 17712.00)` where `remunerable` is the sum of each earning
line item multiplied by its UIF-remunerable fraction:

| Earning type             | Remunerable % |
|--------------------------|---------------|
| `Travel allowance - 80%` | 80%           |
| `Severance Pay`          | 0%            |
| everything else          | 100%          |

`Severance Pay` is a voluntary / loss-of-employment award, explicitly excluded
from the UIF definition of remuneration. R17,712.00 is the monthly remunerable
cap.

Verified: April-2025 Anthorn had gross R7,393.67 and a R500 travel allowance →
`8310 = 7393.67 − 0.20 × 500 = 7293.67`.

### 8320 — UIF total

`round(8310 × 0.01, 2) × 2` — round the 1% employee side, then double for
employee + employer. Verified: 2024 Bonde, `8310 = 9933.52` →
`round(99.3352, 2) = 99.34` → `8320 = 198.68` (a flat `8310 × 0.02` would give
`198.67`, which the real file does **not** have).

## Inclusion rule (strict per-month)

Month M's file contains every employee whose `Earnings → TOTAL` for month M is
greater than zero, declared at month M's figures. A terminated employee
therefore appears in every month they were paid; their final paid month is
their final declaration and carries `8270` + `8280 = 06`.

The supplied `20440843.003` is a 32-record file that additionally swept in one
terminated employee (Kwepile) at his prior-month figure — a manual catch-up. A
clean strict-per-month February 2024 file has 31 records; Kwepile's final
declaration belongs in the January file.
