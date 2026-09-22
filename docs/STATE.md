# Current State — UIF-ektief

> **Working-memory file.** Read this FIRST every session. It's the cheap pointer.
> Full narrative history lives in `PROGRESS.md` (repo root) — read its TAIL
> only when you need the "why" behind a past decision, never the whole file.

_Last updated: 2026-09-22_

## Now
- **Branch:** `period-end-tax-year` at `eafe025` = `origin/main` =
  `origin/period-end-tax-year`. Clean except this `/pause` edit to
  `docs/STATE.md`. (`ektief-main` still points at `a841f45` — stale, harmless.)
- **Doing:** waiting on a **colleague's test of the live Sage PDF input** —
  the one thing still unsmoked. The tax-year fix that shipped alongside it
  (`a841f45..eafe025`) was **smoke-tested by Melton 2026-09-22 and passed** on
  a real client export; the app is working end to end.
- **Why the PDF input needs them specifically:** Melton has no Employee
  Details / Company Details PDFs; the colleague does. Their run *is* the smoke
  test — on failure fix forward, or revert the merge if serious.
- **Their checklist (UI-19 mode, live app):** YTD + Employee Details PDFs →
  IDs, dates, hours, UIF Yes/No match Sage; Company Details PDF fills only
  empty fields, contact = the **UIF** person (right column), not SARS; H/J
  reasons, download, compare to payroll; eDecs ↔ UI-19 switch keeps details.
- **Tax-year fix: DONE.** Real export for period ending `2026/08/31` reads
  "Tax year ending February 2027" and `8070` runs `202603`…`202608`. Needed a
  **Reboot app** first — see the cache flag below.

## Last shipped
- `period-end-tax-year` — **tax year derived from the period-end month**
  (2026-09-22). Fast-forwarded onto `origin/main` (`a841f45..eafe025`), pushed
  by Melton. **Smoke-tested by Melton 2026-09-22 — passed**, on a real client
  export for period ending `2026/08/31`.
  - **Bug, found by Melton:** entering period ending `20260831` (tax year 2027)
    produced `8070` = `202503` for March — the whole file a **full year early**,
    every month, not just March.
  - **Root cause:** `tax_year_end_year` took the calendar year off Sage's
    "Printed for period ending" line **verbatim** and treated it as the tax-year
    END year. That line carries the **payroll period end**, not the year end, so
    it is only right for a Jan/Feb report. Mid-year it returned 2026 where the
    answer is 2027, and `period_code` — itself correct — then subtracted 1 for
    March–December. Hit both readers: `parse_ytd` (CSV) and `parse_sage_pdf` (PDF).
  - **Fix:** `_tax_year_of(year, month)` = `year if month <= 2 else year + 1`,
    in `parse_ytd`, imported by `parse_sage_pdf` (same precedent as
    `_slash_date_to_yyyymmdd`). `parse_standard` (Excel) **untouched** — the
    sheet tab name is the tax year by ruling.
  - **Tests:** 3 new, written first and watched fail (`2026 != 2027`,
    `'202503' != '202603'`). **184 passed / 2 skipped** (was 181/2).
    `sage_pdf_fixtures.ytd_page`/`ytd_pdf` now take a `period_end`.
  - **Blast radius is small by construction:** a February period end takes the
    `month <= 2` branch and returns the **identical** value to before. Everything
    filed to date, both accepted regression samples, and every pre-existing test
    are February — only mid-year reports move, and those were wrong anyway.
  - **`streamlit_app.py:623`** renders "Tax year ending February {N}" — the
    cheapest on-screen confirmation the fix is live.

- `sage-pdf-input` — **Sage report PDF input for the UI-19 form** (2026-09-14).
  `uif/parse_sage_pdf.py` = the standalone script's PDF readers adapted to
  `YtdRecord`/`EmployeeRecord`; optional Company Details PDF pre-fill; eDecs
  refuses PDFs; PDFs pair only with PDFs. Also fixes an order-dependent
  form-state harvest bug latent since `17ce363`. New dep `pdfplumber`.
  Fast-forwarded onto `origin/main` (`fa5636a..a841f45`; feature `a94ef2f`),
  pushed as Elimperio1. **Live build confirmed** in logged-in Chrome (uploaders
  take PDF; UI-19 shows the PDF note + Company Details uploader).
  **NOT smoke-tested.** Claude-run evidence only: 181 passed/2 skipped; parity
  with the script on 3 real YTD PDFs (636 rows, 0 diffs); 23/23 headless flows;
  no eDecs module changed.
- `ui19-pdf` — UI-19 PDF form output mode. Landed `f148f67..fa5636a`,
  smoke-tested by Melton, live; eDecs byte-identical to previous prod.

## Deployment
- Cloud app owned by the **`elimperio1`** Streamlit account (not `thrilla99`):
  `https://uif-003-generator-fgfhue929gfxetywv8kkx7.streamlit.app/`, serves
  `origin/main`, fresh clone each cold start — pushing `main` is all it takes.
  To read/drive it from Chrome, open `.../~/+/` (the app iframe) directly.
- Prod env: Python 3.14.7, streamlit 1.61.1, pandas 3.0.5, openpyxl 3.1.5.
- App is **private** in Cloud (a logged-out `curl` gets **303** to login — not
  a deploy signal). README says "intentionally public-facing". Decide which.

## Next
- Get the colleague's result on the live **Sage PDF input** and record it here
  and in `PROGRESS.md`.
- **Decide: CSV employee-code collision (likely live bug, not fixed).**
  `parse_employee_code` strips leading zeros; real Sage reports hold distinct
  employees `026`/`0026`. If a Sage CSV prints both, the second overwrites the
  first in `parse_ytd`/`parse_employees` and one employee silently drops out of
  the eDecs file and UI-19. Unconfirmed (no Sage CSV here). Fix changes eDecs output.
- First real UI-19 filing from a **Sage CSV** pair: confirm the "Unemployment
  insurance fund" row and "Average working hours per period" are read.
- Suggested, not built: a reconciliation line for why UI-19 and `.NNN` employee
  counts differ; freeze/retire the standalone UI19 script once the PDF input is
  proven (app then covers all of it except the xlsx working copy).
- Parked for Melton's call: `Dismissed → 04` (`ontslaan`) in
  `generate_003.inferred_status_code`; README "public" vs Cloud "private".
- Audit leftovers (product decisions): finding #6 — eDecs `gross > 0` omits
  non-contributors; finding #9 — `8320` round-then-double reproduces Sage.
- On the shelf: nothing unmerged — `period-end-tax-year` is in `main`.
  `ui19-pdf` (local `e952ded`, unpushed), `standard-format`,
  `e03-compliance` are all contained in `main` — safe to delete.

## Open flags
- **Sage PDF input is still unsmoked** — see Now. Don't build on it until the
  colleague's result is in. (The tax-year fix beside it is smoked and passed.)
- **After ANY parser fix, REBOOT the Cloud app — don't just rerun.** The
  tax-year fix read the old value live twice: Streamlit Cloud had not
  redeployed yet, and `@st.cache_data` on `_parse_ytd` (`streamlit_app.py:375`)
  is keyed on file bytes, so a pre-fix upload of the same file returns the
  cached answer **without the parser running at all**. A rerun fixes neither;
  Manage app → Reboot clears both. Cost a false "the fix didn't work".
- **The real-sample eDecs regression CANNOT run on this machine.** The 2 skips
  in `tests/test_regression.py` need `samples/private/ytd_2024.csv` /
  `ytd_2025.csv` / `expected_*.003`, which aren't here (only the standard
  workbook fixtures are). So the tax-year fix was **never checked against a real
  accepted file** — mitigated only by both samples being February filings
  (periods `202402`, `202502`), which take the unchanged branch. A green run
  here is **184 passed / 2 skipped**; if those 2 ever say `passed`, the real
  samples arrived and the check is genuinely covered.
- **Date-derived values need a fixture where the naive rule is WRONG.** Every
  fixture *and* both real samples print `2025/02/28` — February is the one month
  where reading the year verbatim is accidentally correct, which is why
  `tax_year_end_year` was wrong for ten months of the year with 181 tests green.
  Written up in the vault: `03 Memory/Lessons/Verification.md`.
- **Form-state harvest reads only the last-drawn keys** (`drawn_suffix`, set in
  `mode_key`); a Company Details fill bumps `form_generation` (`~N` key suffix).
  Don't widen the harvest to every `@` key — stale undrawn keys linger.
- **PDF reports pair only with PDFs** — PDF codes kept as printed; don't
  normalise them to allow mixing with CSV.
- **Each output mode follows its own rules** (eDecs = E03 spec; UI-19 = the
  standalone script's rules). Don't "harmonise" them.
- Machine RAM is tight (~1 GB free): background Streamlit servers get killed.
- **Local `main` (`19a0ec5`) and `step-1-scaffold` are an UNRELATED abandoned
  history** — never merge. `C:\Projects\uif-003-generator` is that scaffold;
  real work happens in `C:\Projects\uif-ektief`.
- E03 check digit can't validate Elimperio's own reference —
  `uif_ref.check_digit_ok` stays **warning-only**.
- **Do not pin `pandas<3`** — Cloud is Python 3.14, no pandas 2.x wheel.
- Pushes as `Thrilla99` 403 — repo-local credential override in the shared
  `.git/config`; re-apply `credential.https://github.com.helper ""` then
  `--add ... manager` if it regresses.
- Regression data is gitignored: `samples/private/standard_*` (real client
  data, never commit). Real Sage YTD PDFs used for parity live outside the repo
  (Downloads, Desktop `UIF SHIT`) — never copy them in.

---
_Full history → `PROGRESS.md` (read the tail). This file is the pointer; that file is the archive._
