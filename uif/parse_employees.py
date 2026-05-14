"""
Parser for the Sage "Employee Details" CSV.

The Employee Details CSV is a label/value-style report (one row per
attribute, multiple blocks per employee). Key fields used by the .003:

- Employee code   (join key)
- Full names      (first names)
- Employee name   (initial + surname, used to derive surname)
- ID number       (13-digit SA ID; may have a ".00" suffix and lost leading
                   zero from Excel — strip non-digits then left-pad to 13)
- Passport number / Passport country
- Date of birth   (DD/MM/YYYY)
- Date Engaged    (DD/MM/YYYY)
- End date        (DD/MM/YYYY when present)
- Employee status (Normal, Resigned, ...)
- UIF status      (Contributes / Excluded — skip Excluded)

Step 2 will implement this.
"""


def parse(_file_bytes: bytes):
    raise NotImplementedError("Step 2.")
