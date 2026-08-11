"""
Regression checks against the real Standard Format workbooks.

The workbooks and the expected-values sidecar contain real PII, live in
samples/private/ (gitignored), and these tests skip automatically when they
are absent. No real name, ID, or figure may appear in this file — the
expectations load from the sidecar JSON.
"""

import io
import json
from pathlib import Path

import openpyxl
import pytest

from uif import parse_standard

PRIVATE = Path(__file__).resolve().parent.parent / "samples" / "private"
PAYROLL = PRIVATE / "standard_payroll.xlsx"
MASTER = PRIVATE / "standard_master.xlsx"
EXPECTED = PRIVATE / "standard_expected.json"

pytestmark = pytest.mark.skipif(
    not (PAYROLL.exists() and MASTER.exists() and EXPECTED.exists()),
    reason="real Standard Format workbooks not present",
)

EXP = json.loads(EXPECTED.read_text()) if EXPECTED.exists() else {}


def test_master_has_expected_employees():
    records = parse_standard.parse_employees(MASTER.read_bytes())
    assert sorted(records, key=int) == EXP["master_codes"]
    emp1 = records["1"]
    assert emp1.passport_number == EXP["emp1_passport"]
    assert emp1.id_number == ""
    assert emp1.date_of_birth == EXP["emp1_dob"]
    assert records["9"].surname == EXP["emp9_surname"]


def test_payroll_2025_known_figures_and_divergences():
    records, warnings = parse_standard.parse_ytd(PAYROLL.read_bytes(), "2025")
    rec = records["1"]
    # These rows carry stale in-sheet labels but belong to tax year 2025
    # (ruling: tab name + row position; labels are stale).
    assert rec.gross("March") == EXP["y2025_emp1_march_gross"]
    assert rec.gross("October") == EXP["y2025_emp1_october_gross"]
    assert rec.earnings["December"] == EXP["y2025_emp1_december_earnings"]
    assert any(EXP["divergence_fragment"] in w for w in warnings)


def test_sheet_2027_matches_master_sheet2_copy():
    # Sheet2 of the master workbook is an independent copy of the current
    # tax year — cross-check employee 1's March figure against it.
    records, _ = parse_standard.parse_ytd(PAYROLL.read_bytes(), "2027")
    wb = openpyxl.load_workbook(io.BytesIO(MASTER.read_bytes()), data_only=True)
    try:
        expected = round(float(wb["Sheet2"]["B9"].value), 2)
    finally:
        wb.close()
    assert records["1"].gross("March") == expected


def test_all_year_sheets_parse_cleanly():
    data = PAYROLL.read_bytes()
    sheets = parse_standard.list_year_sheets(data)
    assert sheets == EXP["year_sheets"]
    for sheet in sheets:
        records, _ = parse_standard.parse_ytd(data, sheet)
        assert len(records) == EXP["employees_per_sheet"]
