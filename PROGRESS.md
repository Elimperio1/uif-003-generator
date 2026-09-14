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
- Filename extension is now an auto-numbered sequence (`.001`, `.002`, … per
  file in the batch, ordered by tax-year month).
- 2025 Employee Details CSV not yet supplied — 2025 regression test is partial.
- Remunerability map confirmed only for travel allowance + severance.
- Output line order is employee-code order, not Sage's internal order.

## Step 4 — Standard Format input
Status: **complete** (smoke-tested by Melton 2026-08-11, merged to `main`)
Design: `docs/superpowers/specs/2026-08-11-standard-format-design.md`
- New `uif/parse_standard.py`: format detection (zip magic), employee master
  parser ("Employee details" sheet), payroll parser (one sheet per tax year).
- Rulings baked in: tax year from the sheet tab name + month from row
  position (in-sheet labels are stale); UIF recomputed from earning columns
  with soft warnings where the sheet's own UIF column differs.
- Per-file dispatch in the app: Sage CSV and Standard xlsx can be mixed.
  Tax-year selectbox for multi-year workbooks; workbook header shown as a
  hint, never auto-filled.
- `Salaris`/`Leave pay`/`Oortyd`/`Verlof` confirmed fully remunerable;
  `Reistoelaag` deliberately left unknown (warning fires if it appears).
- Real workbooks moved to `samples/private/standard_*.xlsx` (gitignored);
  synthetic-fixture unit tests + private regression tests added.
- Sage pipeline and generation rules untouched; all prior tests pass.

## E03 compliance — second audit pass (2026-08-17)
Status: **awaiting Melton's smoke test** (branch `e03-compliance`, six commits
`38f981b`…`b5af249`, NOT pushed, NOT merged)
A second field-by-field audit against the E03 PDF closed findings 10–15
(`docs/E03-COMPLIANCE.md`). Every new check is **warning-only** — a false
rejection costs the whole filing.
- **A** (`38f981b`) — new `uif/sa_id.py`: Appendix B check digit, Excel
  scientific-notation signature (ID ending in ≥4 zeros), and a `problems()`
  helper. An invalid `8200` now also writes `8220,"<code>"` (rule 8220), and
  `validate.py` warns per problem. Also killed a phantom: comments referenced
  a `is_corrupted_sa_id` that had never been written.
- **B** (`adc8e2f`) — §5 quote/control-char folding: curly `“ ”` and straight
  `"` fold to an apostrophe inside quoted fields; CR/LF/TAB/control chars
  collapse to a space; commas warned about, left unchanged.
- **C** (`e047386`) — §4/§5 zero-field omission: `8300`/`8310`/`8320` and the
  footer totals `8130`/`8135`/`8140` drop out when zero; `8150` always stays.
- **D** (`07d09fe`) — payroll "Reason: Death" now infers `8280 = 02 Deceased`
  (was thrown away); `models.YtdRecord.reason` added.
- **E** (`27b14f3`) — Step 4 no longer pre-selects `06`; the selectbox starts
  empty (death pre-selects `02`), and Step 5 refuses until every termination
  has a reason.
- **F** (`b5af249`) — §8/§9 soft warnings: end-before-start, start-in-future,
  under-15, and over-length email/name/phone. `validate()` gained a
  `period_yyyymm` argument.
- **Diff result:** suite **151 passed, 2 skipped**; app boots HTTP 200; the
  private-workbook byte-comparison changes in only the two spec-required ways —
  zero currency fields drop from empty-month footers (finding 12), and the one
  "Reason: Death" employee (code 3, periods 202301 & 202302) flips
  `8280,06`→`8280,02` (finding 13). No `8220` added on real data. Everything
  else byte-identical.

## UI-19 PDF form output (2026-09-14)
Status: **awaiting Melton's smoke test** (branch `ui19-pdf`, NOT pushed, NOT merged)
Spec `docs/superpowers/specs/2026-09-14-ui19-pdf-design.md`; plan
`docs/superpowers/plans/2026-09-14-ui19-pdf.md`.
- Output toggle: eDecs `.NNN` (unchanged) or the official UI-19 PDF, built with
  the standalone `UI19_Automation_7` script's rules.
- `79de5ce` — parsers keep what the UI-19 needs: Sage YTD "From:" date and the
  "Unemployment insurance fund" deduction row; Employee Details raw name, full
  names, average hours; Standard Format UIF column + `uif_status_reported=False`.
  All new model fields defaulted — eDecs output untouched.
- `f07e91e` — `uif/ui19.py`: script inclusion (paid / UIF deducted / started or
  left in month), name split, dates, contributor Yes/No, warnings; H/J code
  application.
- `ea97f0b` — `uif/ui19_pdf.py` + `uif/assets/`: the script's writer returning
  bytes. Found and fixed a pypdf trap (one reader for all pages repeats every
  row on every page).
- `82e1ba3` — app wiring: UI-19 Steps 2–5, H pickers shared with eDecs keys,
  J pickers, gate, PDF/zip download; form values persist across mode switches.
- **Verified:** suite 169 passed, 2 skipped; rendered PDF inspected; Chrome run
  on synthetic Standard + Sage fixtures in both modes.
- **Smoke PASSED by Melton** on `bc253f4`. Follow-up `17ce363` (asked for
  after the smoke): larger "Start here" card selector for the output mode, and
  form details kept across mode switches. Headless-Chromium flows showed
  `bc253f4` lost the leaver reasons and starting file number on a switch, and
  the first fix lost a field typed just before clicking the switch; `17ce363`
  (per-mode widget keys seeded from `kept_details` + a harvest of pending
  `field@mode` values at the top of each run) keeps everything. Melton
  confirmed it looked good.
- **Shipped 2026-09-14:** before landing, eDecs output was fingerprinted on
  `origin/main` vs the branch (216 `.NNN` files with/without 8280 picks, 108
  validation runs; private Standard workbooks 2022–2027, Standard fixtures,
  synthetic Sage CSVs) — zero differences. Fast-forwarded onto `origin/main`
  (`f148f67..fa5636a`) via `_land`, pushed as Elimperio1; live app showed the
  new selector in logged-in Chrome. `7dbb4b6` (STATE note) pushed to
  `origin/ui19-pdf` only.
