# Current State — UIF-ektief

> **Working-memory file.** Read this FIRST every session. It's the cheap pointer.
> Full narrative history lives in `PROGRESS.md` (repo root) — read its TAIL
> only when you need the "why" behind a past decision, never the whole file.

_Last updated: 2026-10-06 (home PC)_

## Now
- **Branch:** `main` at `6bbe7af`, in sync with `origin/main`. Untracked:
  `EmployeeDetail (8).csv`, `YearToDateDetail (8).csv` (client data, don't commit).
- **Local folders consolidated (2026-10-06):** the three UIF checkouts are now
  one — `C:\Projects\uif-003-generator` on the home PC (`uif-ektief` is gone,
  no extra worktrees), tracking `origin/main` directly. Work PC uses
  `C:\Users\Elimp\Projects\UIF` (clone of the same `origin/main`).
- **Doing:** nothing in flight. Waiting on a re-upload of the VPRO Projects
  master workbook on the live app to confirm the `8b6efb7` fix.
- **Sage PDF input for UI-19 is still NOT SMOKE-TESTED.** Merged 2026-09-14
  at Melton's request so a colleague with real Employee Details / Company
  Details PDFs can test it live. Checklist: UI-19 mode with a real Employee
  Details PDF + YTD PDF (IDs, dates, hours, UIF status come through), a real
  Company Details PDF (fills empty fields only), eDecs still refuses PDFs,
  details survive mode switches. Fix forward or revert if it fails.

- **Possible leavers is NOT SMOKE-TESTED** (`feat/possible-leavers`,
  `e8b60a5`). Merged 2026-10-07 at Melton's request so a colleague can test it
  live. Checklist, both modes: an employee paid earlier but not in a filed
  month, or with an end date while still "Employed", shows under "may have
  left"; no default; a leaving code asks for a last day when none is on file
  and declares them (eDecs 8270/8280, UI-19 column H); 01 changes nothing;
  generation blocked until each is answered; "Leavers and their reasons"
  table lists them. Known limit: eDecs only lists paid months, so a last day
  in an unpaid month isn't declared in eDecs. Fix forward or revert.

## Last shipped
- `feat/possible-leavers` (2026-10-07): `uif/leavers.py` flags possible
  leavers; `possible_leaver_pickers` / `leaver_summary` in `streamlit_app.py`;
  payroll "Reason:" text shown beside each leaver. Not smoke-tested (see Now).
- `4f85b4c` merge (fix `48d3804`, 2026-10-06): Employee Details CSV reads
  year-first dates (`2024/04/01`) as well as `DD/MM/YYYY` —
  `_ddmmyyyy_to_yyyymmdd` in `uif/parse_employees.py`. ADVISEIT export had
  blank DOB/start dates. **Live-confirmed by Melton after a Reboot app.**
- On the shelf: `fix/clear-parse-cache-on-parser-change` (`a9d89fd`) — clears
  `st.cache_data` when `uif/*.py` changes, so parser fixes don't need a
  reboot. AppTest-verified, suite green, NOT merged — Melton's call.
- `8b6efb7` fix: Standard Format master sheet found regardless of case and
  spaces (VPRO's tab is `" Employee Details"`), and date cells in General
  format (Excel serials) read as dates instead of blank. `uif/parse_standard.py`
  (`parse_employees`, `_date`), test in `tests/test_parse_standard.py`.
  Pushed to `origin/main`; suite 181 passed, 6 skipped. Cloud redeploy not
  verified. (work PC)
- `f9b42ed` merge (2026-09-25): app only opens for links minted by the
  practice-management app (`app_link.py`, feature `fda28d5`). Also `eafe025`
  (2026-09-22): tax year derived from the period-end month. Neither is in
  `PROGRESS.md` yet.
- `sage-pdf-input` (`a94ef2f`) and `ui19-pdf` (`fa5636a`), 2026-09-14: detail
  in `PROGRESS.md`.

## Deployment
- Cloud app owned by the **`elimperio1`** Streamlit account (not `thrilla99`):
  `https://uif-003-generator-fgfhue929gfxetywv8kkx7.streamlit.app/`, serves
  `origin/main`, fresh clone each cold start — pushing `main` is all it takes.
- Prod env: Python 3.14.7, streamlit 1.61.1, pandas 3.0.5, openpyxl 3.1.5.
- App is **private** in Cloud (a logged-out `curl` gets **303** to login — not
  a deploy signal). README says "intentionally public-facing". Decide which.

## Next
- Confirm the VPRO master workbook now loads on the live app.
- Record `eafe025`, `fda28d5` and `8b6efb7` in `PROGRESS.md`.
- Get the colleague's smoke result on the live Sage PDF input (checklist under
  Now) and record it here and in `PROGRESS.md`.
- **Decide: CSV employee-code collision (likely live bug, not fixed).**
  `parse_employee_code` strips leading zeros, and real Sage reports hold
  distinct employees `026`/`0026` (seen in the PDFs). If a Sage CSV prints both,
  the second record overwrites the first in `parse_ytd`/`parse_employees` and
  one employee silently drops out of the eDecs file and UI-19. No Sage CSV on
  this machine to confirm what the CSV prints. Fixing it changes eDecs output.
- First real UI-19 filing from a **Sage CSV** pair: confirm the "Unemployment
  insurance fund" row and "Average working hours per period" are read (never
  seen in a real CSV on this machine).
- Suggested, not built: a reconciliation line explaining why UI-19 and `.NNN`
  employee counts differ; freeze/retire the standalone UI19 script once the
  PDF input is live (the app then covers everything it does except the xlsx
  working copy).
- Parked for Melton's call: `Dismissed → 04` (`ontslaan`) in
  `generate_003.inferred_status_code` (changes no-override output); README
  "public" vs Cloud "private".
- Audit leftovers (product decisions, not bugs): finding #6 — spec wants all
  employees monthly, app's eDecs `gross > 0` rule omits non-contributors;
  finding #9 — `8320` round-then-double reproduces Sage, keep unless SARS objects.
- On the shelf: nothing unmerged. Leftover local branches after the folder
  merge — `standard-format`, `e03-compliance`, `ektief-main`, `sage-pdf-input`,
  `ui19-pdf`, `feat/app-link-gate`, `period-end-tax-year`. All merged except
  `period-end-tax-year`: 2 docs-only commits ahead (`e7f2bc2` tax-year smoke
  pass + reboot-not-rerun rule, `0c0423b` STATE snapshot). Fold `e7f2bc2`'s
  smoke note into `PROGRESS.md` if wanted, then delete the lot.

## Open flags
- **Form-state harvest reads only the last-drawn keys** (`drawn_suffix`, set in
  `mode_key`). Widget keys of a mode not drawn since linger in session state
  with old values; harvesting them all made persistence depend on key order.
  Don't widen the harvest back to every `@` key.
- **PDF reports pair only with PDFs.** PDF codes are kept as printed; the
  CSV/xlsx parsers normalise leading zeros. Don't normalise the PDF side to
  "allow mixing" — it merges distinct employees.
- **Each output mode follows its own rules — keep it that way.** eDecs = E03
  spec (`generate_003` / `validate`); UI-19 = the standalone script's rules
  (unpaid starters/leavers included, UIF Yes/No from status, script layout
  quirks like the UIF ref overflowing the branch box). Don't "harmonise" them.
- **Home PC:** local `main` is now the real `origin/main` history. Branch
  `step-1-scaffold` (`00fc59d`) is still the UNRELATED abandoned scaffold —
  never merge; safe to delete.
- **Work PC needed `pip install -r requirements.txt`** before the PDF test
  modules would import (pdfplumber, reportlab, pypdf).
- **E03 check digit can't validate Elimperio's own reference** (spec publishes a
  6-digit-base routine only) — `uif_ref.check_digit_ok` stays **warning-only**.
- **Do not pin `pandas<3`** — Cloud is Python 3.14, no pandas 2.x wheel.
- **Pushes as `Thrilla99` 403** — repo-local credential override in the shared
  `.git/config` fixes it; re-apply `credential.https://github.com.helper ""` then
  `--add ... manager` if it regresses.
- **Regression data is gitignored:** `samples/private/standard_*` (real client
  data, never commit). Test skips are absent private samples (2 on the other machine, 6 here).
- Reading the E03 spec PDF needs `pypdf` locally (now also an app dep).

---
_Full history → `PROGRESS.md` (read the tail). This file is the pointer; that file is the archive._
