# Current State — UIF-ektief

> **Working-memory file.** Read this FIRST every session. It's the cheap pointer.
> Full narrative history lives in `PROGRESS.md` (repo root) — read its TAIL
> only when you need the "why" behind a past decision, never the whole file.

_Last updated: 2026-09-22_

## Now
- **Branch:** `period-end-tax-year` at `e7f2bc2`, clean tree, **1 ahead of
  `origin/main`** (`eafe025`) — a docs-only commit, unpushed. Push with
  `git push origin period-end-tax-year:main`.
- **Doing:** waiting on a **colleague's test of the live Sage PDF input** — the
  only unsmoked thing in prod. Melton has no Employee Details / Company Details
  PDFs; the colleague does, so their run *is* the smoke test. On failure fix
  forward, or revert the merge if serious.
- **Their checklist (UI-19 mode, live app):** YTD + Employee Details PDFs →
  IDs, dates, hours, UIF Yes/No match Sage; Company Details PDF fills only
  empty fields, contact = the **UIF** person (right column), not SARS; H/J
  reasons, download, compare to payroll; eDecs ↔ UI-19 switch keeps details.
- `ektief-main` is stale at `a841f45`; `git branch -f ektief-main origin/main`.

## Last shipped
- `period-end-tax-year` — **tax year derived from the period-end month**, not
  the year alone (2026-09-22). Fixed `tax_year_end_year` in `parse_ytd` +
  `parse_sage_pdf`: a mid-year Sage export put every `8070` a full calendar
  year early. `a841f45..eafe025`. **Smoke-tested by Melton — passed**, on a
  real export for period ending `2026/08/31`. Detail in `PROGRESS.md`.
- `sage-pdf-input` — Sage report PDFs as UI-19 input (2026-09-14).
  `uif/parse_sage_pdf.py`; PDFs pair only with PDFs; eDecs refuses them. Also
  fixed an order-dependent form-state harvest bug latent since `17ce363`.
  `fa5636a..a841f45` (feature `a94ef2f`). **NOT smoke-tested** — see Now.

## Deployment
- Cloud app owned by the **`elimperio1`** Streamlit account (not `thrilla99`):
  `https://uif-003-generator-fgfhue929gfxetywv8kkx7.streamlit.app/`, serves
  `origin/main`, fresh clone each cold start.
  To read/drive it from Chrome, open `.../~/+/` (the app iframe) directly.
- **Pushing `main` is not enough to verify a parser fix.** Cloud redeploys on
  its own schedule, and `@st.cache_data` on `_parse_ytd` (`streamlit_app.py:375`)
  is keyed on the uploaded file's bytes — a pre-fix upload of the same file
  returns the cached answer without the parser running. **Manage app → Reboot**
  clears both. This cost a false "the fix didn't work" on 2026-09-22.
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
  the eDecs file and UI-19. Fix changes eDecs output. **Now cheap to confirm:**
  a real Sage CSV pair sits in `Downloads/YearToDateDetail (8).csv` +
  `EmployeeDetail (8).csv` (Irma Palm Creations, period ending 2026/08/31).
- First real UI-19 filing from a **Sage CSV** pair: confirm the "Unemployment
  insurance fund" row and "Average working hours per period" are read.
- Suggested, not built: a reconciliation line for why UI-19 and `.NNN` employee
  counts differ; freeze/retire the standalone UI19 script once the PDF input is
  proven (app then covers all of it except the xlsx working copy).
- Parked for Melton's call: `Dismissed → 04` (`ontslaan`) in
  `generate_003.inferred_status_code`; README "public" vs Cloud "private".
- Audit leftovers (product decisions): finding #6 — eDecs `gross > 0` omits
  non-contributors; finding #9 — `8320` round-then-double reproduces Sage.
- On the shelf: `period-end-tax-year` (`e7f2bc2`, docs commit unpushed).
  `ui19-pdf` (local `e952ded`, unpushed), `standard-format`, `e03-compliance`
  are all contained in `main` — safe to delete.

## Open flags
- **Sage PDF input is still unsmoked** — see Now. Don't build on it until the
  colleague's result is in.
- **The real-sample eDecs regression CANNOT run on this machine.** The 2 skips
  in `tests/test_regression.py` want `samples/private/ytd_2024.csv` /
  `ytd_2025.csv` / `expected_*.003`, which aren't here. A green run is
  **184 passed / 2 skipped**; if those 2 ever say `passed`, the real samples
  arrived and the comparison is genuinely covered.
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
  data, never commit). Real Sage exports used for parity live outside the repo
  (Downloads, Desktop `UIF SHIT`) — never copy them in.

---
_Full history → `PROGRESS.md` (read the tail). This file is the pointer; that file is the archive._
