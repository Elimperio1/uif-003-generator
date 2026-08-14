# Current State — UIF-ektief

> **Working-memory file.** Read this FIRST every session. It's the cheap pointer.
> Full narrative history lives in `PROGRESS.md` (repo root) — read its TAIL
> only when you need the "why" behind a past decision, never the whole file.

_Last updated: 2026-08-14_

## Now
- **Branch:** `e03-compliance`, branched off `ektief-main`/`cef1435`.
  **Committed but NOT pushed and NOT merged** — waiting on Melton's smoke test.
- **Doing:** E03 spec compliance fixes. 8 of the 9 findings in
  `docs/E03-COMPLIANCE.md` are closed; #9 deliberately left alone.
- **Smoke-test checklist** (the parts automated tests cannot reach):
  1. Upload the two Standard Format workbooks, pick tax year **2023** — that
     is the only sheet with terminations, so it is the one that shows the new
     Step-4 panel. 4 employees should be listed with a `06 Resigned` dropdown.
  2. Change one to `11 Retrenched`, confirm the preview's `Status (8280)`
     column follows and the amber "will be declared as 06 Resigned" count drops.
  3. Type the UIF reference **with a slash** (`2044084/3`) and confirm the app
     reports it will be sent as `020440843` and the download is
     `20440843.001` — the old code produced `2044084/3.001`, an invalid name.
  4. Set "Starting file number" to something other than 1 and confirm the
     filenames follow.

## Last shipped
- `standard-format` — Standard Format xlsx input (Step 4): `uif/parse_standard.py`
  (detection + employee-master + payroll parsers), per-file dispatch and
  tax-year picker in `streamlit_app.py`, `openpyxl` dep, synthetic-fixture tests
  + private regression suite. Fast-forwarded to `main` (head `96a2c70`, feature
  work `de95166`→`54e6d0c`), pushed to `origin/main` 2026-08-11.
  **Deploy confirmed live 2026-08-14** (see Deployment).
- `4f9982d` — output filename changed to `<uifref-no-leading-zero>.NNN` with
  batch-sequence numbering. This is the commit that introduced compliance
  gaps #3 and #4 in `docs/E03-COMPLIANCE.md`.

## Deployment (confirmed live 2026-08-14)
- Cloud app is owned by the **`elimperio1`** Streamlit account, NOT `thrilla99`
  — that workspace has no UIF app, so looking there suggests it's undeployed.
- Dashboard: `uif-003-generator · main · streamlit_app.py`
  → `https://uif-003-generator-fgfhue929gfxetywv8kkx7.streamlit.app/`
- Serves `origin/main`; boot log shows a fresh clone each cold start, so
  pushing to `origin/main` is all that's needed. `step-1-scaffold` is deployed
  nowhere.
- Prod env: **Python 3.14.7**, streamlit 1.61.1, pandas 3.0.5, openpyxl 3.1.5.
  Step 4 is live — both uploaders accept CSV + XLSX.
- App is **private** in Cloud settings (viewers need a Streamlit login), which
  contradicts README's "intentionally public-facing". Decide which is right.

## Next
- **Smoke-test `e03-compliance`, then push + merge.** Nothing else is queued.
- Still open from the audit: finding #6's wider half — the spec wants details
  for **all** employees monthly "irrespective of whether they are contributors
  or non-contributors", but the app's `gross > 0` inclusion rule omits
  non-contributors because that is what Sage exports. Product decision, not a
  bug.
- Finding #9 (`8320` round-then-double vs strict 2%) stays as-is: it
  reproduces Sage and matches the verified samples. Only revisit if SARS
  objects.
- Optional: repo-local credential fix so pushes stop 403-ing (see Open flags).

## Open flags
- **Do not pin `pandas<3`.** Prod is Python 3.14, which has **no pandas 2.x
  wheel** (`pip download` finds zero candidates) — that pin breaks the deploy.
  `requirements.txt` is now `pandas>=3.0,<4`; local runs 3.0.3, prod 3.0.5.
  Going to pandas 2 would also require pinning Python to 3.12 on Cloud.
  Local suite passes on this pin: **89 passed, 2 skipped**. Pushed in `340643a`
  and the Cloud rebuild was watched through to a clean boot on 2026-08-14 —
  prod serves the app normally on the new range.
- **Pushes 403 as `Thrilla99` — FIXED 2026-08-14.** gh CLI's global helper was
  overriding Windows Credential Manager (which holds the Elimperio1
  credential). Repo-local override now set in `.git/config`, and `340643a`
  pushed cleanly with a plain `git push origin ektief-main:main`. If it ever
  regresses, re-apply:
  `git config --local credential.https://github.com.helper ""`
  then `git config --local --add credential.https://github.com.helper manager`.
  Note this lives in the shared `.git` at `C:\Projects\uif-003-generator`, so
  it covers both worktrees.
- **Local `main` (19a0ec5) and the `step-1-scaffold` worktree are an UNRELATED
  abandoned scaffold history — never merge them into anything** (see memory
  note "prod-vs-local-unrelated-repos"). Confirmed 2026-08-14: no common
  ancestor with `origin/main`. Prod tracks `origin/main` via `ektief-main`.
  The second worktree lives at `C:\Projects\uif-003-generator` — that's why
  there appear to be two `streamlit_app.py` files; it's one repo, two checkouts.
- `standard-format` branch is fully merged (same SHA as `ektief-main`) — safe
  to delete whenever.
- Regression tests need the gitignored private files:
  `samples/private/standard_payroll.xlsx`, `standard_master.xlsx`,
  `standard_expected.json` (real client data — never commit; `*.xlsx` is
  gitignored as a tripwire). Tests skip cleanly when absent — those are the
  2 skips.
- Known data quirks in the Standard workbooks (all handled + warned in-app):
  stale month labels on 2025–2027 sheets, 6 manually-adjusted UIF months,
  4 months where the sheet forgot the R17,712 cap, ex-employees paid
  Jan/Feb 2023 after 2022 end dates.

---
_Full history → `PROGRESS.md` (read the tail). This file is the pointer; that file is the archive._
