# Current State — UIF-ektief

> **Working-memory file.** Read this FIRST every session. It's the cheap pointer.
> Full narrative history lives in `PROGRESS.md` (repo root) — read its TAIL
> only when you need the "why" behind a past decision, never the whole file.

_Last updated: 2026-08-17_

## Now
- **SHIPPED & LIVE (2026-08-17).** `e03-compliance` (`f148f67`) was
  smoke-tested, pushed, and fast-forwarded onto `origin/main`
  (`cef1435..f148f67 e03-compliance -> main`). Prod (Streamlit Cloud, serves
  `origin/main`) re-clones on the next cold start; the live app returned
  **HTTP 200** right after the push. `ektief-main` moved to match. The branch
  survives on the remote as `origin/e03-compliance`. Pushed as **Elimperio1**.
- **What changed (second pass, 2026-08-17):** findings **10–15** in
  `docs/E03-COMPLIANCE.md` are closed, one commit per finding —
  A `38f981b` SA ID validation (rule 8200 + Appendix B) + 8220-when-invalid;
  B `adc8e2f` quote/control-char folding (§5); C `e047386` zero-field omission
  (§4/§5); D `07d09fe` payroll "Reason: Death" → `02 Deceased` (rule 8280);
  E `27b14f3` Step 4 no longer pre-selects `06`; F `b5af249` §8/§9 soft
  warnings (dates, under-15, field lengths). Every new check is warning-only.
- **Verified (automated + smoke, all passed):**
  suite **151 passed, 2 skipped**; `grep is_corrupted_sa_id` empty; app boots
  headless HTTP 200; and the byte-comparison on the real private workbooks
  (all 12 months × tax years 2022–2027, no overrides) changes in **only** the
  two spec-required ways — zero currency fields drop out of empty-month footers
  (finding 12), and the one "Reason: Death" employee (code 3, periods 202301 &
  202302) flips `8280,06` → `8280,02` (finding 13). No `8220` was added on real
  data (every real ID is valid with a matching DOB). Everything else is
  byte-identical.
- **Smoke test — PASSED 2026-08-17** (Melton in-browser; also re-run by Claude
  in Chrome against synthetic PII-free workbooks — empty dropdown, "— not set",
  the Step-5 gate, death→02 pre-select, the scientific-notation ID warning
  naming the employee with 8200+8220, and the slash-reference/filename all
  confirmed). The items that were checked:
  1. Load the two Standard Format workbooks, tax year **2023** — the sheet with
     terminations, so the one that shows the Step-4 panel. Each termination's
     reason dropdown now starts **empty** (no pre-selected `06`).
  2. Pick a reason (e.g. `11 Retrenched`); the preview's `Status (8280)` column
     should follow, showing `— not set` until you choose, and the amber
     "N will be declared as 06 Resigned" count reflects only the ones you set
     to `06`.
  3. Enter the UIF reference **with a slash** (`2044084/3`) — the app should
     say it will be sent as `020440843` and the download should be
     `20440843.001`. The old code produced `2044084/3.001`, an invalid name.
  4. Set "Starting file number" above 1 and confirm the filenames follow.
  5. In the master workbook, mangle one ID to scientific notation in Excel
     (e.g. format the cell as a number so it shows like `8.5E+12`) and
     re-upload — confirm the amber warning **names the employee** and the file
     still generates, with both `8200,<id>` and `8220,"<code>"` on that record.
  6. Confirm a termination selectbox starts empty and **Step 5 refuses to
     generate** ("Select a reason … for every employee who has left") until
     every termination has a reason.
  7. If the workbook contains a death, confirm it arrives **pre-selected as
     `02 Deceased`** in Step 4.

## Last shipped
- `e03-compliance` — the full E03 compliance work (first pass findings 1–9 in
  `48acab1`, second pass findings 10–15 in `38f981b`…`f148f67`). Fast-forwarded
  onto `origin/main` on **2026-08-17** (`cef1435..f148f67`); live app HTTP 200
  after the push. Branch kept at `origin/e03-compliance`.
- `standard-format` — Standard Format xlsx input (Step 4): `uif/parse_standard.py`
  (detection + employee-master + payroll parsers), per-file dispatch and
  tax-year picker in `streamlit_app.py`, `openpyxl` dep, synthetic-fixture tests
  + private regression suite. Fast-forwarded to `main` (head `96a2c70`, feature
  work `de95166`→`54e6d0c`), pushed to `origin/main` 2026-08-11.
  **Deploy confirmed live 2026-08-14** (see Deployment).
- `4f9982d` — output filename changed to `<uifref-no-leading-zero>.NNN` with
  batch-sequence numbering. This is the commit that introduced compliance
  gaps #3 and #4 in `docs/E03-COMPLIANCE.md`; both are fixed on
  `e03-compliance`.

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
- **This STATE update still needs to ship.** The deploy already landed, but this
  file's "shipped + live" edit is uncommitted. Commit it and push from
  `C:\Projects\uif-ektief`: `git add docs/STATE.md && git commit` then
  `git push origin e03-compliance:main` (still a clean fast-forward), or just
  `git push origin HEAD:main` once committed on `e03-compliance`.
- Optional deeper deploy check: after Cloud finishes re-cloning (a couple of
  minutes), drive the **live** app once with synthetic workbooks to confirm the
  new build (not just the shell) is serving — HTTP 200 alone only proves
  reachability.
- Still open from the audit: finding #6's wider half — the spec wants details
  for **all** employees monthly "irrespective of whether they are contributors
  or non-contributors", but the app's `gross > 0` inclusion rule omits
  non-contributors because that is what Sage exports. Product decision, not a
  bug.
- Finding #9 (`8320` round-then-double vs strict 2%) stays as-is: it
  reproduces Sage and matches the verified samples. Only revisit if SARS
  objects.

## Open flags
- **The E03 check digit cannot validate Elimperio's own reference.** Appendix A
  reproduces its worked example exactly (`2648757` → check digit 7) but
  publishes multipliers for a **6-digit base only**; `2044084/3` has 7, and
  five candidate extensions all fail. `uif/uif_ref.check_digit_ok` returns
  `None` for those and the check is **warning-only**. Do not "fix" this into a
  blocking rule — it would reject valid submissions.
- **Do not pin `pandas<3`.** Prod is Python 3.14, which has **no pandas 2.x
  wheel** (`pip download` finds zero candidates) — that pin breaks the deploy.
  `requirements.txt` is now `pandas>=3.0,<4`; local runs 3.0.3, prod 3.0.5.
  Going to pandas 2 would also require pinning Python to 3.12 on Cloud.
  Pushed in `340643a` and the Cloud rebuild was watched through to a clean
  boot on 2026-08-14 — prod serves the app normally on the new range.
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
- `standard-format` branch is fully merged (same SHA as `96a2c70`, an ancestor
  of `ektief-main`) — safe to delete whenever.
- Regression tests need the gitignored private files:
  `samples/private/standard_payroll.xlsx`, `standard_master.xlsx`,
  `standard_expected.json` (real client data — never commit; `*.xlsx` is
  gitignored as a tripwire). The **2 skips are the Sage CSV samples**
  (`ytd_2024.csv` etc.), which are genuinely absent; the Standard Format
  private suite does run.
- Reading the spec PDF needs `pypdf` (`pip install pypdf`) — there is no
  poppler on this machine, so `Read` cannot render it. Deliberately **not** in
  `requirements.txt`; it is a dev convenience, not an app dependency.
- Known data quirks in the Standard workbooks (all handled + warned in-app):
  stale month labels on 2025–2027 sheets, 6 manually-adjusted UIF months,
  4 months where the sheet forgot the R17,712 cap, ex-employees paid
  Jan/Feb 2023 after 2022 end dates.

---
_Full history → `PROGRESS.md` (read the tail). This file is the pointer; that file is the archive._
