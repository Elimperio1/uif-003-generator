# SARS UIF Declaration File — Format Specification

The UIF declaration is a flat text file with three record types: a header
(`UICR`), one or more employee records (`UIWK`), and a footer (`UIEM`). It is
submitted to SARS via uFiling.

This spec is verified against two real Sage exports:
`20440843.003` (period 202402) and `20440843.004` (period 202502).

## Encoding & line endings

- latin-1 / ISO-8859-1 encoding
- CRLF (`\r\n`) line terminators on **every** line, including the footer
  (the file ends with a trailing `\r\n`)

Each record is a single line of comma-separated `<field_code>,<value>` pairs.
String values are double-quoted; numeric values are not.

## Filename

`<UIF reference number with leading zeros stripped>.<NNN>`, where `NNN` is the
file's 1-indexed position within the current generation batch, zero-padded to
three digits. Batches are ordered by tax-year month (March first, February
last). Generating a single month produces `<ref>.001`; a full tax year produces
`<ref>.001` through `<ref>.012`. e.g. `20440843.001`. The earlier `.003` /
`.004` Sage exports happened to fit this convention because they were the
third and fourth submissions of a sequence.

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

## Employee record (UIWK)

One per included employee. Field order:
`8001, 8110, [8200|8210], 8230, 8240, 8250, 8260, [8270], 8280, 8300, 8310, 8320`

| Code | Description                              | Required  | Example          |
|------|------------------------------------------|-----------|------------------|
| 8001 | Record identifier                        | const     | `"UIWK"`         |
| 8110 | UIF reference (matches header 8020)      | yes       | `"020440843"`    |
| 8200 | SA ID number, 13 digits, **unquoted**    | one of    | `8306056177085`  |
| 8210 | Passport number, **quoted**              | 8200/8210 | `"BN487879"`     |
| 8230 | Surname                                  | yes       | `"Anthorn"`      |
| 8240 | First name (truncated to 12 chars)       | yes       | `"Sibonile"`     |
| 8250 | Date of birth (YYYYMMDD)                 | yes       | `19830605`       |
| 8260 | Employment start date (YYYYMMDD)         | yes       | `20230824`       |
| 8270 | Employment end date (YYYYMMDD)           | if term'd | `20231231`       |
| 8280 | Employee status code                     | yes       | `01`             |
| 8300 | Gross earnings for the period            | yes       | `11550`          |
| 8310 | UIF remuneration (see below)             | yes       | `11550`          |
| 8320 | UIF total (see below)                    | yes       | `231`            |

`8200` is preferred when present; otherwise `8210`. ID numbers preserve leading
zeros and are unquoted. Passports are quoted verbatim (they may contain letters
and hyphens, e.g. `"12-135849P-12"`).

### Status codes (field 8280)

`01` for employed / normal / new staff; `06` for terminated ("No longer
employed"). `8270` is present only when `8280 = 06`. Other SARS codes exist but
are not exercised by the current data.

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
