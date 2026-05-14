# Build Progress

## Step 1 — Scaffold
Status: **complete** (merged to `main`)
- Project skeleton, requirements, .gitignore
- Streamlit entry point with shared-password auth gate
- Two file-upload widgets and intro instructions
- Stub modules, FORMAT.md, README

## Step 2 — Full pipeline (parsers, matcher, validator, generator, UI)
Status: **awaiting deploy + smoke test**
Branch: `step-2-pipeline`
Design: `docs/superpowers/specs/2026-05-14-uif-003-step-2-design.md`
Scope:
- `uif/models.py` — dataclasses, constants, the UIF-remunerability map
- `uif/parse_ytd.py` — Year to Date Detail parser (+ tax-year detection)
- `uif/parse_employees.py` — Employee Details parser
- `uif/match.py` — join on employee code
- `uif/generate_003.py` — declaration file builder (strict per-month)
- `uif/validate.py` — blocking errors vs soft warnings
- `streamlit_app.py` — company-config form, month picker, preview, download
- `FORMAT.md` rewritten with the rules verified against two real Sage samples
- Tests + `samples/anonymize.py` (fixtures generated from real exports placed
  in `samples/private/`)

Reverse-engineered and confirmed against two Sage sample sets:
- 2024: `YearToDateDetail (2).csv` + `EmployeeDetail (1)2024.csv` + `20440843.003`
- 2025: `YearToDateDetail (3).csv` + `20440843.004` + `UIFExportDetail 2025.pdf`

Key rules locked in this step:
- `8310` = `min(gross − non-remunerable earnings, 17712)`; `Travel allowance
  - 80%` is 80% remunerable, `Severance Pay` 0%, everything else 100%.
- `8320` = `round(8310 × 0.01, 2) × 2`.
- Strict per-month inclusion: an employee is in month M's file iff their
  Earnings TOTAL for M is greater than zero.

Known open items (see the design doc's Risks section):
- File extension (`.003` vs `.004`) — exposed as a config field, default `003`.
- 2025 Employee Details CSV not yet supplied — 2025 regression test is partial.
- Remunerability map confirmed only for travel allowance + severance.
- Output line order is employee-code order, not Sage's internal order.

## Step 3 — Polish (planned)
- Resolve open items above once more sample data / answers arrive
- Tighten the remunerability map as real exports reveal new earning types
