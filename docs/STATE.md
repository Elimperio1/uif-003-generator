# Current State — UIF-ektief

> **Working-memory file.** Read this FIRST every session. It's the cheap pointer.
> Full narrative history lives in `PROGRESS.md` (repo root) — read its TAIL
> only when you need the "why" behind a past decision, never the whole file.

_Last updated: 2026-09-14_

## Now
- **SHIPPED & LIVE (2026-09-14).** `ui19-pdf` fast-forwarded onto
  `origin/main` (`f148f67..fa5636a`, via a `_land` branch at `origin/main`),
  pushed as Elimperio1; branch kept at `origin/ui19-pdf`; `ektief-main` moved
  to `fa5636a`. The live app (logged-in Chrome) shows the new "Start here"
  selector, so the build — including the new `reportlab`/`pypdf` deps —
  installed and booted on Cloud. Melton smoke-tested both `bc253f4` and the
  selector/persistence follow-up `17ce363`.
- **eDecs proven unchanged before landing:** `generate_003.build` (default and
  picked 8280 overrides) + `validate` + parse warnings fingerprinted on
  `origin/main` vs the branch — 216 files / 108 validation runs across the
  private Standard workbooks (every sheet 2022–2027, every month), the
  Standard fixtures and the synthetic Sage CSVs: **zero differences**.
- **UI-19 PDF form output mode** (spec
  `docs/superpowers/specs/2026-09-14-ui19-pdf-design.md`, plan
  `docs/superpowers/plans/2026-09-14-ui19-pdf.md`). An **Output** toggle
  switches the app between the eDecs `.NNN` file (unchanged) and the official
  UI-19 PDF, filled using the rules of the standalone script at
  `C:\Projects\UI19_Automation_7` (its `pdf_writer.py` + layout + official PDF
  ported into `uif/ui19_pdf.py` / `uif/assets/`; its row rules into
  `uif/ui19.py`). Commits `79de5ce` parsers · `f07e91e` rules · `ea97f0b` PDF
  writer · `82e1ba3` app. New deps `reportlab>=4.4,<6`, `pypdf>=6,<7`
  (pure-Python wheels, confirmed for Python 3.14).
- **Each mode keeps its own rules** — UI-19 declares starters/leavers in the
  month even if unpaid, takes UIF Yes/No from UIF status (Standard Format: the
  UIF column), dates prefer Employee Details. Approved deviations from the
  script: H prefilled from the Step 4 reason (leading zero dropped), J picker
  per non-contributor per month (6 preselected when no pay), `mt` added to the
  title list, passport-overflow warning.
- **Verified by Claude (supporting evidence, not sign-off):** suite **169
  passed, 2 skipped** (incl. the private Standard regression); rendered sample
  PDF inspected — values land in their boxes, 7 rows → 2 pages; Chrome run on
  synthetic Standard + Sage fixtures: both modes, H gate, zip download button,
  values kept across mode switches, eDecs still excludes the unpaid leaver.
- **Smoke PASSED by Melton (2026-09-14)** on `bc253f4`. He then asked for a
  larger mode selector and for details to persist across mode switches:
  `17ce363` (NOT yet smoke-tested). Persistence = per-mode widget keys seeded
  from `st.session_state["kept_details"]`, plus a harvest of pending
  `field@mode` values at the top of every run. Headless-Chromium flows showed
  the previous commit lost the H reasons and starting file number on a switch;
  `17ce363` keeps everything, including a field typed just before clicking the
  switch.
- **Smoke checklist for Melton:** a real month in UI-19 mode — open the PDF and
  compare to the payroll; a real **Sage CSV** pair to confirm the
  "Unemployment insurance fund" row and "Average working hours per period" are
  read (no Sage CSV sample exists locally); eDecs output for the same month
  unchanged.

## Previously shipped (e03-compliance)
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
- **Smoke test — PASSED 2026-08-17** (Melton in-browser + a Claude-in-Chrome
  re-run on synthetic PII-free workbooks): empty termination dropdown, preview
  `— not set`, the Step-5 gate refusing until every leaver is set, death
  pre-selected `02 Deceased`, the scientific-notation ID warning naming the
  employee with `8200`+`8220`, and the slash-reference → `001234567` /
  `01234567.001` filename all confirmed.

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
- First real UI-19 filing from a **Sage CSV** pair: confirm the "Unemployment
  insurance fund" row and "Average working hours per period" come through
  (never seen in a real CSV on this machine).
- Suggested, not built (2026-09-14): a reconciliation line explaining why the
  UI-19 and `.NNN` employee counts differ; retire/freeze the standalone UI19
  script once live (it only adds Sage **PDF** input); Company Details PDF
  auto-fill for the UI-19 employer fields.
- Optional deeper deploy check: drive the **live** app once with synthetic
  workbooks to confirm the new build (not just the shell) is serving — HTTP 200
  alone only proves reachability.
- Parked for Melton's call: wire `Dismissed → 04` (Afrikaans `ontslaan`) into
  `generate_003.inferred_status_code` — deferred because it would change the
  no-override output; reconcile README "public" vs Cloud "private" setting.
- Still open from the audit: finding #6's wider half — the spec wants details
  for **all** employees monthly "irrespective of whether they are contributors
  or non-contributors", but the app's `gross > 0` inclusion rule omits
  non-contributors because that is what Sage exports. Product decision, not a
  bug.
- Finding #9 (`8320` round-then-double vs strict 2%) stays as-is: it
  reproduces Sage and matches the verified samples. Only revisit if SARS
  objects.

## Open flags
- **UI-19 layout quirks are the script's, kept on purpose:** the UIF ref's
  check digit overflows into the branch-number box; termination dates sit a
  little wider than the printed D D M M Y Y headings.
- **pypdf page trap:** adding pages from ONE `PdfReader` of the blank form
  shares their content stream, so every overlay lands on every page.
  `ui19_pdf.write_pdf` opens a fresh reader per page — keep it that way
  (`test_each_page_carries_only_its_own_rows` guards it).
- **`2281bf3` (STATE "shipped" note) is on `origin/e03-compliance` and local
  `ektief-main` but NOT on `origin/main`** — deliberate. It is docs-only, so it
  was kept off `main` to avoid a needless Cloud redeploy. `ektief-main` therefore
  reads `[ahead 1]` of `origin/main`; that is expected, not drift. The functional
  deploy on `origin/main` is `f148f67`.
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
