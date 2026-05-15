# Build Progress

## Step 1 — Scaffold
Status: **complete** (merged to `main`)
- Project skeleton, requirements, .gitignore
- Streamlit entry point with shared-password auth gate (later removed in step 3)
- Two file-upload widgets and intro instructions
- Stub modules, FORMAT.md, README

## Step 2 — Full pipeline (parsers, matcher, validator, generator, UI)
Status: **complete** (merged to `main`)
Design: `docs/superpowers/specs/2026-05-14-uif-003-step-2-design.md`
- `uif/models.py`, `parse_ytd.py`, `parse_employees.py`, `match.py`,
  `validate.py`, `generate_003.py`
- Streamlit UI wired end-to-end: form, month picker, preview, download
- FORMAT.md rewritten against two real Sage samples (2024 `.003` and 2025 `.004`)
- Unit + regression tests added
- Post-merge follow-up fixes:
  - Name parsing: first name = leading token of "Full names"; surname = trailing
    token(s) of "Employee name" with compound-particle absorption
    (`van Wyk`, `van der Merwe`)
  - UIF rounding: `8320` now computes each 1% half with `ROUND_HALF_UP` (Decimal)
    and sums, matching Sage exactly (Qotoyi 6492.50 → 129.86, not 129.84)

Key rules locked in this step:
- `8310` = `min(gross − non-remunerable earnings, 17712)`; `Travel allowance
  - 80%` is 80% remunerable, `Severance Pay` 0%, everything else 100%.
- `8320` = `ROUND_HALF_UP(8310 × 0.01, 2) × 2` (Decimal, not float).
- Strict per-month inclusion: an employee is in month M's file iff their
  Earnings TOTAL for M is greater than zero.

## Step 3 — Rename, deauth, redesign
Status: **awaiting deploy + smoke test**
- Renamed app to **UIF-ektief** (Afrikaans pun on *effektief*).
- Removed the shared-password gate; app is now public.
- Visual redesign using the *impeccable* skill's design laws:
  warm off-white background, single warm-amber accent, Fraunces wordmark with
  italic "ektief", Inter for body, restrained colour strategy, no card grids,
  no gradient text, no em dashes in UI copy.

## Known open items (carried forward)
- File extension (`.003` vs `.004`) is a config field defaulting to `003`.
- 2025 Employee Details CSV not yet supplied — 2025 regression test is partial.
- Remunerability map confirmed only for travel allowance + severance.
- Output line order is employee-code order, not Sage's internal order.
