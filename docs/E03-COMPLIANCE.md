# E03 spec compliance — audit 2026-08-14

Generator (`uif/generate_003.py`, `uif/models.py`, `uif/validate.py`,
`streamlit_app.py`) compared field by field against
`ELECTRONIC DECLARATION SPECIFICATIONS - E03 (1).pdf` (UIF, version E031,
16 Sept 2002, mandatory from 1 April 2003).

**Nothing here is fixed yet.** Ranked by consequence.

## Already correct

Record structure and sequence (UICR → UIWK… → UIEM), the `8000`/`8010`/`8015`
constants, field order within each record, `8200` unquoted vs `8210` quoted,
CRLF terminators, and the number format — spec §5 requires no decimal point
when there are no cents, which is exactly what `_fmt` does by stripping a
trailing `.00`. The `8270`-only-when-status-is-not-`01` rule also matches.

## 1. `8020` is never normalised — whole-file rejection

`streamlit_app.py:417` does `.strip()` and nothing else. Spec §8 requires 9
chars, zero-filled from the left, non-numeric characters excluded
(`123456/8` → `001234568`). An invalid `8020` rejects **the entire file**.
Entering `20440843` or `204408/43` kills the submission with no warning from
the app. Appendix A of the PDF has the check-digit algorithm.

## 2. `8280` declares every termination as "Resigned"

`models.py:60` maps both `No longer employed` and `Terminated` → `06`. In the
spec `06` is specifically **Resigned**; there is no generic "no longer
employed" code. Dismissed is `04`, contract expired `05`, retrenched `11`,
deceased `02`, business closed `14`.

This produces **no SARS warning** — `06` is a valid code, so it is accepted
silently as a resignation. Since resignation generally disqualifies a UIF
claim, this can block ex-employees' benefits. Sage's status text is too coarse
to resolve automatically; likely needs a per-employee override in the UI.

## 3. File sequence always restarts at `.001`

`streamlit_app.py:506` uses `enumerate(ordered_months, start=1)`, so every
batch starts over. Spec §12/§13: a repeated filename means "the last file
received will be used, and it will overwrite all previously sent files with
the same file name". Generate March–Feb, then generate a correction batch, and
the second run silently overwrites the first at SARS. The Step-1 scaffold had a
user-set starting batch number; it was dropped in `4f9982d`.

## 4. `build_filename` diverges from spec §12

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

`validate.py:49` raises a **blocking** error when an employee has neither ID
nor passport, stopping generation entirely. The spec provides `8220`
(Alternate Number) for exactly this case — "the personnel, clock card or
payroll number" — and a record is only rejected when *none* of `8200`/`8210`/
`8220` is present. `MatchedRecord.employee_code` already holds the payroll
number. One extra field turns a hard block into a valid submission.

## 6. No `8290` reason-for-non-contribution

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

`generate_003.py:145` slices first names to 12. Spec allows Alphanumeric 90.
Needless data loss.

## 8. Output is latin-1, spec says ASCII

`generate_003.py:179` encodes latin-1. Spec §5: "The file must be submitted in
ASCII format." Any accented surname emits a non-ASCII byte.

## 9. `8320` is round-then-double, not exactly 2% of `8310`

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
