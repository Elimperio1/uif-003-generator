# Current State — UIF-ektief

> **Working-memory file.** Read this FIRST every session. It's the cheap pointer.
> Full narrative history lives in `PROGRESS.md` (repo root) — read its TAIL
> only when you need the "why" behind a past decision, never the whole file.

_Last updated: 2026-09-14_

## Now
- **Branch:** `sage-pdf-input`, cut from local `ui19-pdf` (`e952ded`, the
  `/pause` docs commit, NOT pushed) which is docs-only ahead of `origin/main`
  (`fa5636a`). Feature commit on top. **NOT pushed, NOT merged.**
- **Doing:** **Sage PDF input for the UI-19 form — awaiting Melton's smoke
  test.** The standalone script's own input (Year to Date Detail + Employee
  Details PDFs, optional Company Details PDF) now works in the app's UI-19
  mode. `uif/parse_sage_pdf.py` = the script's PDF readers, adapted to
  `YtdRecord`/`EmployeeRecord`. New dep `pdfplumber>=0.11,<0.12`. Detail in
  `PROGRESS.md` (tail).
- **Smoke checklist for Melton:** UI-19 mode with a real **Employee Details
  PDF** + YTD PDF (never seen here — IDs, dates, hours, UIF status must come
  through), and a real **Company Details PDF** (fills empty fields only, UIF
  contact from the right-hand column); eDecs mode still works with CSV/xlsx and
  refuses PDFs; details survive switching modes back and forth.
- **Local servers:** `localhost:8501` = this branch (restart it after any edit;
  a long-running dev server served stale code this session).

## Last shipped
- `ui19-pdf` — **UI-19 PDF form output mode** (2026-09-14). "Start here" card
  selector: eDecs `.NNN` (unchanged) or the official UI-19 PDF, filled with the
  standalone script's rules (`C:\Projects\UI19_Automation_7`, untouched).
  `uif/ui19.py` (row rules), `uif/ui19_pdf.py` + `uif/assets/` (form writer),
  parser fields for UIF deduction / start date / raw names / hours; H and J
  reason pickers; details kept across mode switches (per-mode widget keys
  seeded from `st.session_state["kept_details"]` + a harvest at the top of each
  run). New deps `reportlab>=4.4,<6`, `pypdf>=6,<7`. Spec/plan in
  `docs/superpowers/{specs,plans}/2026-09-14-ui19-pdf*`.
  Fast-forwarded onto `origin/main` (`f148f67..fa5636a`; feature commits
  `79de5ce`…`17ce363`), pushed as Elimperio1. **Smoke-tested by Melton**
  (`bc253f4`, then `17ce363`). Live app confirmed in logged-in Chrome showing
  the new selector (so the deps installed on Cloud). **eDecs byte-identical**
  to previous prod: 216 files + 108 validation runs, zero differences.
- `e03-compliance` — full E03 compliance (findings 1–15). Fast-forwarded onto
  `origin/main` 2026-08-17 (`cef1435..f148f67`), smoke-tested, live.

## Deployment
- Cloud app owned by the **`elimperio1`** Streamlit account (not `thrilla99`):
  `https://uif-003-generator-fgfhue929gfxetywv8kkx7.streamlit.app/`, serves
  `origin/main`, fresh clone each cold start — pushing `main` is all it takes.
- Prod env: Python 3.14.7, streamlit 1.61.1, pandas 3.0.5, openpyxl 3.1.5.
- App is **private** in Cloud (a logged-out `curl` gets **303** to login — not
  a deploy signal). README says "intentionally public-facing". Decide which.

## Next
- Smoke-test `sage-pdf-input` (checklist under Now), then land it the usual way
  (temp `_land` branch at `origin/main`, fast-forward, push as Elimperio1).
  The branch carries the docs-only `e952ded` too — harmless.
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
- On the shelf: nothing unmerged. `standard-format` and `e03-compliance` are
  fully merged — safe to delete.

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
- **Local `main` (`19a0ec5`) and `step-1-scaffold` are an UNRELATED abandoned
  history** — never merge. The second worktree `C:\Projects\uif-003-generator`
  is that scaffold; real work happens here in `C:\Projects\uif-ektief`.
- **E03 check digit can't validate Elimperio's own reference** (spec publishes a
  6-digit-base routine only) — `uif_ref.check_digit_ok` stays **warning-only**.
- **Do not pin `pandas<3`** — Cloud is Python 3.14, no pandas 2.x wheel.
- **Pushes as `Thrilla99` 403** — repo-local credential override in the shared
  `.git/config` fixes it; re-apply `credential.https://github.com.helper ""` then
  `--add ... manager` if it regresses.
- **Regression data is gitignored:** `samples/private/standard_*` (real client
  data, never commit). The 2 test skips are the absent Sage CSV samples.
- Reading the E03 spec PDF needs `pypdf` locally (now also an app dep).

---
_Full history → `PROGRESS.md` (read the tail). This file is the pointer; that file is the archive._
