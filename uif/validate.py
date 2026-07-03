"""
Validate joined records and return a list of human-readable soft errors,
plus a list of errors that should block file generation outright.

Checks (see FORMAT.md, "Validation rules"):

- Identity: each employee needs a 13-digit SA ID (8200) or a passport
  number (8210), plus DOB and employment-start dates.
- Rule D: zero contribution (8320 == 0.00) without a non-contribution
  reason code (8290 in 1-6) is an error; a reason code alongside a
  non-zero contribution is also an error.
- Status: 8280 must be a valid 01-19 code; terminated statuses need an
  end date unless Rule A blanked it for this period.
- Financial: 8310 <= 17712.00 cap, 8320 == round(8310 * 0.02, 2).

Step 2 will implement this.
"""


def validate(_records) -> tuple[list[str], list[str]]:
    raise NotImplementedError("Step 2.")
