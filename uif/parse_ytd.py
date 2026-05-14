"""
Parser for the Sage "Year to Date Detail" CSV.

The YTD CSV is a wide report with one block per employee. Each block has:
- An "Employee code" header row.
- An "Employee name" row.
- 12 monthly columns spanning the SA tax year (March -> February).
- A "TOTAL" row giving gross earnings per month.
- Multiple "Deductions" and "Company Contributions" rows; we care about the
  "Unemployment insurance fund" entries for both.

Step 2 will implement this.
"""


def parse(_file_bytes: bytes):
    raise NotImplementedError("Step 2.")
