# E03 spec compliance — audit 2026-08-14

Generator (`uif/generate_003.py`, `uif/models.py`, `uif/validate.py`,
`streamlit_app.py`) compared field by field against
`ELECTRONIC DECLARATION SPECIFICATIONS - E03 (1).pdf` (UIF, version E031,
16 Sept 2002, mandatory from 1 April 2003).

**Status: findings 1, 3, 4, 5, 6, 7 and 8 fixed on branch `e03-compliance`
(2026-08-14). Finding 2 fixed as a UI override. Finding 9 deliberately left
as-is. A second pass (2026-08-17) closed findings 10–15 on the same branch —
SA ID validation, quote/control-char folding, zero-field omission,
reason→status inference, the removal of the pre-selected `06`, and a batch of
§8/§9 soft warnings.** Ranked by consequence; each section records what was
done.

Verified after the fixes: on the real private workbooks, with the reference
entered in the form the old code expected and no status overrides, the
first-pass fixes left the generated files **byte-identical to the previous
output** for tax years 2023, 2024 and 2025. The second pass (findings 10–15)
changes the output in only the two ways the spec requires: zero currency fields
and their codes drop out (finding 12), and the single payroll "Reason: Death"
employee is now declared `02 Deceased` instead of `06` (finding 13). Every
other byte is unchanged. The new rules only change the cases that were
previously wrong.

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

---

# Second pass — 2026-08-17

Findings 10–15 come from a second field-by-field audit. Same ranking by
consequence; each carries the spec rule it enforces and a "Fixed —" line. Every
new check is **warning-only** — a false rejection costs the whole filing.

## 10. `8200` is never validated — an Excel-mangled ID is emitted unchanged

**Fixed** — new `uif/sa_id.py` implements the Appendix B check digit, an Excel
scientific-notation signature (a 13-digit ID ending in four or more zeros), and
a `problems()` helper (not-13-digits, bad check digit, the Excel signature, or
first six digits not matching the date of birth). `generate_003.build()` now
writes `8220,"<employee code>"` alongside `8200` whenever the ID fails
validation, and `validate.py` raises one soft warning per problem, each
spelling out the consequence.

No ID validation existed anywhere. `parse_employees.py` referred to a
"corruption detector" `is_corrupted_sa_id` that **had never been written**
(grep confirmed), so an Excel-mangled ID (`8.30606E+12` → `8306060000000`) was
emitted as `8200` unchanged. Spec rule 8200 + Appendix B: an invalid ID is a
warning, the record is held in a secondary database, and the employee cannot
claim until it is corrected. Spec rule 8220: "This field is mandatory if fields
8200 or 8210 are invalid or not present." `8306060000000` passes the check
digit by coincidence — the Excel signature is why the check digit alone is not
enough.

## 11. Curly and straight quotes break a quoted field (spec §5)

**Fixed** — `_ASCII_FALLBACKS` now maps the curly double quotes `“ ”` to an
apostrophe (not a straight `"`), and a new `_sanitise()` used by `_q`/`_field`
replaces any remaining straight `"` with `'` and collapses control characters
(`\r`, `\n`, `\t`, anything `< 0x20` or `0x7f`) to a single space, with the
length cut applied afterwards.

Spec §5 wraps alphanumeric fields in double quotes and defines no escaping.
`_q('O“Reilly”')` previously returned `"O"Reilly""` — an embedded straight
quote — and a stray newline in a surname would split the record onto a new
line. Commas inside a quoted field are left unchanged (the spec defines no
escaping); `validate.py` warns instead so the filer can confirm SARS accepts
it.

## 12. Zero-valued money fields were written, not omitted (spec §4 + §5)

**Fixed** — `8300`, `8310` and `8320` are each omitted when zero; the footer
totals `8130`, `8135` and `8140` are each omitted when their sum is zero; `8150`
(the record count) is always written.

Spec §4: "If a field is blank or zero it should be omitted from the SARS format
along with its associated code." §5: "The absence of the code and its
associated field value implies a zero." The severance-only case previously
wrote `8310,0` and `8320,0`, drawing SARS warnings on `8290`, `8300`, `8310`
and `8320` at once; it now emits `8290,06` and `8300,<gross>` with `8310` and
`8320` omitted. On the private data this also strips `8130,0`/`8135,0`/`8140,0`
from the footer of every month with no employees.

## 13. The payroll "Reason: Death" was read and thrown away (spec §8, rule 8280)

**Fixed** — `models.YtdRecord` gains a `reason` field, `parse_standard` stores
the raw "Reason:" value, and `generate_003.inferred_status_code()` maps
death/deceased/oorlede/afgesterf/dood → `02`. `default_status_code()` now
prefers the inferred code, so `build()` with no override declares a death as
`02 Deceased` (spec code 02) instead of the generic `06`.

The old code read the "Reason:" only to emit a warning that said "the
declaration uses status 06, the same as any other termination" — no longer
true. Only death is inferred automatically. The private workbook also contains
a "Dismissed" reason, which maps cleanly to `04 Dismissed` (Afrikaans
`ontslaan`) — that mapping is **left for the filer to confirm** rather than
wired in, because a wrong 8280 is accepted silently by SARS and costs an
ex-employee their claim, and activating it would change the no-override output.

## 14. Step 4 pre-selected `06 Resigned` (spec §8, rule 8280)

**Fixed** — each termination selectbox now starts empty (unless the payroll
file justifies a code — a death pre-selects `02`), `status_overrides` carries
only employees the filer actually chose, the preview shows "— not set" until a
code is picked, and a UI gate refuses to generate until every termination has a
reason.

A pre-selected `06` with an amber count is what gets clicked past, and `06`
(Resigned) generally disqualifies a UIF claim. This follows Melton's tax-year
picker precedent (no default). `build()` with no overrides is unchanged, so the
verified output and the byte-comparison are unaffected.

## 15. Cheap §8/§9 warnings SARS would otherwise return (spec §8/§9)

**Fixed** — `validate.py` adds soft warnings for: an end date (`8270`) before
the start date (`8260`); a start date after the last day of the declared period
("dated in the future"); a date of birth (`8250`) implying the employee is
younger than 15 on the last day of the period; and a header/footer email,
contact name or phone longer than the spec's field length (each is truncated on
output, so the warning stops a cut email being a surprise).

`validate()` gained a `period_yyyymm` parameter for the date checks (default
`None` keeps every existing caller working); the app passes `periods[month]`.
All soft, none blocking.
