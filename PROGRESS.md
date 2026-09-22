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
Status: **shipped and live 2026-09-14** (see the last bullet)
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

## Sage PDF input for the UI-19 form (2026-09-14)
Status: **merged to `main` and live 2026-09-14, NOT smoke-tested** (merged at Melton's
explicit request so a colleague with the real Employee Details / Company Details
PDFs can test it on the live app; Melton has none)
Bounded change, design approved in chat (no spec/plan doc): the standalone
script's own input, the Sage report PDFs, now works in the app's UI-19 mode.
- `uif/parse_sage_pdf.py` — the script's `parse_ytd_detail`,
  `parse_employee_detail`, `parse_company_detail` and page tests, regexes
  unchanged, reading bytes; adapters to `YtdRecord` / `EmployeeRecord` so
  `ui19.form_rows` runs as-is. `page.close()` per page: 68-page report peak
  ~213 MB -> ~8 MB. New dep `pdfplumber>=0.11,<0.12` (3.14 wheels checked).
- **Codes kept as printed.** Parity on the real PDFs first failed: Sage has
  distinct employees `026`/`0026`, `045`/`0045`, `01`/`001`, and the CSV
  parsers' leading-zero normalisation merged them (one record overwrote the
  other). So PDF pairs with PDF only; a PDF + CSV mix is refused.
- App: uploaders take `.pdf`; eDecs refuses PDFs (YTD PDF has only the
  earnings TOTAL); wrong-box / non-Sage PDFs refused; optional Company Details
  PDF fills **empty** employer fields once per file.
- Pre-fill needed new widget keys (a redrawn text input ignores a changed
  `value=`): a `~N` generation suffix on `mode_key`, bumped by the fill.
- **Found and fixed a latent bug from `17ce363`:** the top-of-run harvest read
  every `field@mode` key, but keys of a mode not drawn since linger with old
  values, so the result depended on key order. On this branch an edit in UI-19
  was undone by switching back to eDecs (prod passes only by key order). The
  harvest now reads only the keys of the last-drawn mode/generation
  (`drawn_suffix`, recorded by `mode_key`).
- **Verified (supporting evidence, not sign-off):** suite 181 passed, 2
  skipped (12 new); parity vs the standalone script on 3 real YTD PDFs, all 36
  month forms, 636 rows: zero differences; headless-Chromium flows 23/23
  (both modes, fill keeps typed values, switches before/after a fill, un-entered
  typing before a switch, H/J, download, mixed/swapped refusals, real 68-page
  YTD in 8.6 s); mode-switch flow 3/3. No tracked eDecs module changed.
- **Not verifiable here:** no real Employee Details or Company Details PDF on
  this machine; those readers are proven only on synthetic PDFs.

## Tax year from the period-end month (2026-09-22)
Status: **merged to `main`, live, and smoke-tested by Melton 2026-09-22**
(pushed unsmoked at his explicit request so a colleague could test; he then
smoked it himself on a real client export before they got to it)
Melton hit it filing for period ending `20260831` (tax year 2027): field
`8070` came out `202503` for March. Not just March — **every month in the
file was a full calendar year early**, January and February included.
- **Root cause, one line.** `parse_ytd.tax_year_end_year` read the year off
  Sage's "Printed for period ending" line **verbatim** and returned it as the
  tax-year END year. That line carries the **payroll period end**, not the
  year end, so it is only right for a January/February report. Printed
  `2026/08/31` it returned 2026 where the answer is 2027, and `period_code` —
  itself correct — then subtracted 1 for March–December.
- `parse_sage_pdf.tax_year_end_year` had the identical bug (`[:4]`), so both
  the CSV and PDF inputs were affected. `parse_standard` (Excel) was not: the
  sheet tab name is the tax year by ruling.
- **Fix:** `_tax_year_of(year, month)` = `year if month <= 2 else year + 1`,
  living in `parse_ytd` and imported by `parse_sage_pdf`, the same precedent
  as `_slash_date_to_yyyymmdd`.
- **Why 181 green tests missed it.** Every fixture *and* both real accepted
  regression samples print `2025/02/28`. February is the one month where
  reading the year verbatim is accidentally correct — the suite had a single
  input value sitting exactly where the bug is invisible. `sage_pdf_fixtures`
  now takes a `period_end` so both cases are reachable. Written up as a
  universal rule in the vault (`03 Memory/Lessons/Verification.md`): a
  date-derived value needs a fixture where the naive rule is WRONG.
- **Verified:** 3 tests written first and watched fail (`2026 != 2027`,
  `'202503' != '202603'`); suite 184 passed / 2 skipped (was 181/2). The 2
  skips are `test_regression.py` — the real-sample eDecs comparison, whose
  `samples/private/ytd_*.csv` are not on this machine, so the fix was never
  checked against a real accepted file. Mitigated by construction: both
  samples are February filings (`202402`, `202502`) and take the unchanged
  `month <= 2` branch.
- **First live attempt read 2026 anyway** — not a code fault. Streamlit Cloud
  had not redeployed, and `@st.cache_data` on `_parse_ytd` is keyed on file
  bytes, so a pre-fix upload of the same file returns the cached `2026`
  without the parser running. A **Reboot app** clears both. Worth remembering:
  after any parser fix, reboot rather than rerun.
- Landed `a841f45..eafe025` (fast-forward, no target checkout), pushed by
  Melton as Elimperio1.
