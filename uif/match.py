"""
Join the YTD payroll data with the employee master on `employee_code`.

Returns a list of fully-populated employee records ready for eDecs
emission, plus a list of soft-error messages for any employees that
are missing required identity fields (ID/passport, DOB, etc).

Zero-contribution employees are kept in the join — Rule D (FORMAT.md)
requires them in the file with a non-contribution reason code (8290),
not silently dropped.

Step 2 will implement this.
"""


def join(_ytd, _employees):
    raise NotImplementedError("Step 2.")
