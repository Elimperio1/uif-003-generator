# Samples

## Regression testing with real Sage exports

`tests/test_regression.py` validates the app's output against real Sage files.
Because those files contain real PII, they live in `samples/private/` — a
gitignored folder that never leaves your machine. The regression tests skip
automatically when the files aren't present.

To run the regression tests, drop your real exports here with these names:

    samples/private/ytd_2024.csv         Year to Date Detail (tax year 2024)
    samples/private/employees_2024.csv   Employee Details (tax year 2024)
    samples/private/expected_2024.003    the real Sage .003 (period 202402)
    samples/private/ytd_2025.csv         Year to Date Detail (tax year 2025)
    samples/private/employees_2025.csv   Employee Details (tax year 2025)
    samples/private/expected_2025.004    the real Sage .004 (period 202502)
    samples/private/standard_payroll.xlsx   Standard Format payroll workbook (one sheet per tax year)
    samples/private/standard_master.xlsx    Standard Format employee master ("Employee details" sheet)

`tests/test_standard_regression.py` uses the two Standard Format workbooks
the same way: it skips automatically when they are absent.

The test rebuilds each month's file from the CSVs and checks that every
employee it produces appears in the real Sage file with identical
8300 / 8310 / 8320 values. (It is structural, not byte-exact, so it isn't
thrown off by Sage's internal line ordering or the one manual catch-up record
in the 2024 file.)

## Anonymised public fixtures

A future step will add `samples/anonymize.py` to derive scrubbed, committable
fixtures from `samples/private/` (scrambled names / IDs / addresses, real
amounts kept) so the regression suite can also run in CI without any PII.
