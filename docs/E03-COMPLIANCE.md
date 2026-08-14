# E03 spec compliance — audit 2026-08-14

Generator (`uif/generate_003.py`, `uif/models.py`, `uif/validate.py`,
`streamlit_app.py`) compared field by field against
`ELECTRONIC DECLARATION SPECIFICATIONS - E03 (1).pdf` (UIF, version E031,
16 Sept 2002, mandatory from 1 April 2003).

**Status: findings 1, 3, 4, 5, 6, 7 and 8 fixed on branch `e03-compliance`
(2026-08-14). Finding 2 fixed as a UI override. Finding 9 deliberately left
as-is.** Ranked by consequence; each section records what was done.

Verified after the fixes: on the real private workbooks, with the reference
entered in the form the old code expected and no status overrides, the
generated files are **byte-identical to the previous output** for tax years
2023, 2024 and 2025. The new rules only change the cases that were previously
wrong.

An addition to the audit: the Appendix A check-digit routine reproduces the
spec's own worked example exactly (`2648757` → base `264875` → total 27 →
check digit 7), but **no straightforward extension of it validates the real
client reference `020440843`**. Appendix A defines multipliers for a six-digit
base only; `2044084/3` has seven. Five candidate extensions were tried and
none yields the expected `3`. The check is therefore warning-only and applies
only to six-digit-base references — wiring it in as a blocking rule would have
rejected Elimperio's own valid reference number.

## Already correct

Record structure and sequence (UICR → UIWK… → UIEM), the `8000`/`8010`/`8015`
constants, field order within each record, `8200` unquoted vs `8210` quoted,
CRLF terminators, and the number format — spec §5 requires no decimal point
when there are no cents, which is exactly what `_fmt` does by stripping a
trailing `.00`. The `8270`-only-when-status-is-not-`01` rule also matches.

## 1. `8020` is never normalised — whole-file rejection

**Fixed** — `uif/uif_ref.py`. `normalise()` strips non-numerics and zero-fills
to 9; the app shows the normalised value and warns on an over-long reference
or a failed check digit. Never blocking (see the check-digit note above).

`streamlit_app.py:417` does `.strip()` and nothing else. Spec §8 requires 9
chars, zero-filled from the left, non-numeric characters excluded
(`123456/8` → `001234568`). An invalid `8020` rejects **the entire file**.
Entering `20440843` or `204408/43` kills the submission with no warning from
the app. Appendix A of the PDF has the check-digit algorithm.

## 2. `8280` declares every termination as "Resigned"

**Fixed as a UI override** — Step 4 now lists every employee declared as
having left and offers the full spec §8 code list per employee, feeding
`build(..., status_overrides=...)`. `06` stays pre-selected so existing
verified output is unchanged, and a warning counts how many are still on it.
Selecting `01`, `09` or `10` also drops `8270`, per the §9 warning table.

`models.py:60` maps both `No longer employed` and `Terminated` → `06`. In the
spec `06` is specifically **Resigned**; there is no generic "no longer
employed" code. Dismissed is `04`, contract expired `05`, retrenched `11`,
deceased `02`, business closed `14`.

This produces **no SARS warning** — `06` is a valid code, so it is accepted
silently as a resignation. Since resignation generally disqualifies a UIF
claim, this can block ex-employees' benefits. Sage's status text is too coarse
to resolve automatically; likely needs a per-employee override in the UI.

## 3. File sequence always restarts at `.001`

**Fixed** — Step 5 has a "Starting file number" input (default 1, capped so
the batch cannot run past `.999`), with the overwrite rule stated above it.

`streamlit_app.py:506` uses `enumerate(ordered_months, start=1)`, so every
batch starts over. Spec §12/§13: a repeated filename means "the last file
received will be used, and it will overwrite all previously sent files with
the same file name". Generate March–Feb, then generate a correction batch, and
the second run silently overwrites the first at SARS. The Step-1 scaffold had a
user-set starting batch number; it was dropped in `4f9982d`.

## 4. `build_filename` diverges from spec §12

**Fixed** — now takes the last 8 digits of the normalised reference.
`tests/test_filename.py` was rewritten around the spec's own worked example
(`1234567/8` → `12345678.003`), which the old rule turned into the invalid
filename `1234567/8.003`.

Spec: `uuuuuuuu.nnn`, where `uuuuuuuu` is **the last 8 digits** of `8020`,
slash excluded. `generate_003.py:69` uses `lstrip("0")` instead. Verified:

| `8020`      | got          | want         |          |
|-------------|--------------|--------------|----------|
| `012345678` | `12345678`   | `12345678`   | OK (spec's own example, ref 1234567/8) |
| `020440843` | `20440843`   | `20440843`   | OK (the one real sample it was built on) |
| `000123456` | `123456`     | `00123456`   | diverges |
| `123456789` | `123456789`  | `23456789`   | diverges |

The two rules agree only for a ref shaped `0` + 8 digits. `tests/test_filename.py:9`
and `:13` assert the divergent behaviour, so it is locked in — fixing the code
means fixing those tests too.

## 5. No `8220` fallback — blocks the file unnecessarily

**Fixed** — `8220` is filled from the employee code when there is no ID and
no passport, and `validate.py` downgrades that case from blocking to a
warning that names the payroll number used.

`validate.py:49` raises a **blocking** error when an employee has neither ID
nor passport, stopping generation entirely. The spec provides `8220`
(Alternate Number) for exactly this case — "the personnel, clock card or
payroll number" — and a record is only rejected when *none* of `8200`/`8210`/
`8220` is present. `MatchedRecord.employee_code` already holds the payroll
number. One extra field turns a hard block into a valid submission.

## 6. No `8290` reason-for-non-contribution

**Fixed for the reachable path** — `8290 = 06` is emitted whenever `8320` is
zero, and the existing soft warning now names the code so it can be checked.
The wider judgement call — whether to declare non-contributing employees the
app currently omits, since Sage does not export them — is unchanged and still
open.

Required whenever the UIF contribution is zero. Reachable today:
`validate.py:66` already detects gross > 0 with remunerable == 0 (e.g. pure
severance) and warns. That path emits `8320 = 0` with no `8290`, drawing SARS
warnings on `8290`, `8300`, `8310` and `8320`.

Related, and a judgement call rather than a bug: the spec's introduction
requires details for **all** employees every month "irrespective of whether
they are contributors or non-contributors", with code `06` = "no income paid
for the payroll period". The app's `gross > 0` inclusion rule omits them. This
matches what Sage exports, which is why it was built that way.

## 7. `8240` truncated to 12 characters

**Fixed** — first names now run to the declared 90 characters, and `8230`,
`8210`, `8220`, `8040`, `8050`, `8060` and `8160` are cut to their own
declared lengths rather than left unbounded (`models.FIELD_LENGTHS`).

`generate_003.py:145` slices first names to 12. Spec allows Alphanumeric 90.
Needless data loss.

## 8. Output is latin-1, spec says ASCII

**Fixed** — output encodes ASCII. `generate_003.to_ascii` transliterates
first (NFKD plus a small map for ø/æ/ß and friends), so `Böhme` becomes
`Bohme` rather than `B?hme`.

`generate_003.py:179` encodes latin-1. Spec §5: "The file must be submitted in
ASCII format." Any accented surname emits a non-ASCII byte.

## 9. `8320` is round-then-double, not exactly 2% of `8310`

**Left as-is, deliberately** — see the reasoning at the end of this section.

Spec §8: "this amount must be 2% of the remuneration subject to UIF" —
a mismatch is a warning, not a rejection. Verified:

| `8310`     | app      | strict 2% |          |
|------------|----------|-----------|----------|
| `9933.52`  | `198.68` | `198.67`  | diverges |
| `7293.67`  | `145.88` | `145.87`  | diverges |
| `11550.00` | `231.00` | `231.00`  | OK       |

Deliberate — it reproduces Sage's round-each-half-then-sum, and `FORMAT.md`
records that the real `.003` file has `198.68`. Recommend leaving as-is unless
SARS objects; changing it would break parity with the verified samples.
