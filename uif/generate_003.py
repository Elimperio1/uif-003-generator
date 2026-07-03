"""
Build a SARS UIF eDecs declaration file from joined records for a single
month. See FORMAT.md for the field-by-field specification.

Structure: one 8000 header, one 8001 row per employee, one 8002 footer
carrying record count and sums of 8300/8310/8320 (footer must balance
the body before output is sealed).

Generation-time rules (FORMAT.md, "Validation rules"):

- Rule A: if a record's termination date (8270) falls after the last
  calendar day of the period (8070), force status 8280 to 01, emit 8270
  blank, and contribute normally for that month.
- Rule B: 8300/8310/8320 always formatted with exactly 2 decimals
  ("17712.00", never "17712").
- Rule C: one record per CRLF-terminated line, no value wrapping or
  fragmentation; no trailing newline after the footer.
- Rule D: 8320 == 0.00 -> 8290 must carry a reason code 1-6;
  8320 > 0 -> 8290 emitted blank.

The file is named `uuuuuuuu.nnn`: 8-digit UIF registration number
(slash stripped) + user-supplied sequential batch number.

Step 2 will implement this.
"""


def build(_records, _period: str, _company) -> bytes:
    raise NotImplementedError("Step 2.")
