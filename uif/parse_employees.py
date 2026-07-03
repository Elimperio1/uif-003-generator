"""
Parser for the Sage "Employee Details" CSV.

The Employee Details CSV is a label/value-style report (one row per
attribute, multiple blocks per employee). Key fields used by the eDecs
file (see FORMAT.md):

- Employee code   (join key; also emitted as field 8220 personnel number)
- Full names      (first names, 8240)
- Employee name   (initial + surname, used to derive surname, 8230)
- ID number       (13-digit SA ID, 8200; may have a ".00" suffix and lost
                   leading zero from Excel — strip non-digits then
                   left-pad to 13)
- Passport number / Passport country (8210, mandatory if no SA ID)
- Date of birth   (DD/MM/YYYY -> CCYYMMDD, 8250)
- Date Engaged    (DD/MM/YYYY -> CCYYMMDD, 8260)
- End date        (DD/MM/YYYY when present -> 8270, subject to Rule A)
- Employee status (Normal -> 01, Resigned -> 06; full 01-19 matrix in
                   FORMAT.md)
- UIF status      (Contributes / Excluded — zero-contribution employees
                   stay in the file with a 8290 reason code per Rule D)

Step 2 will implement this.
"""


def parse(_file_bytes: bytes):
    raise NotImplementedError("Step 2.")
