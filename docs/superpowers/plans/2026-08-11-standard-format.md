# Standard Format Input Support — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Accept "Standard Format" xlsx workbooks (hand-kept payroll + employee master) as an alternative input, parsed into the existing `YtdRecord`/`EmployeeRecord` models so match → validate → generate stay untouched.

**Architecture:** One new module `uif/parse_standard.py` holds format detection and both xlsx parsers. `streamlit_app.py` dispatches per uploaded file on a byte signature. Test fixtures build synthetic workbooks in memory; the real workbooks (PII) move to `samples/private/` and drive an optional regression test.

**Tech Stack:** Python 3.12, openpyxl, Streamlit, pytest. Spec: `docs/superpowers/specs/2026-08-11-standard-format-design.md`.

## Global Constraints

- **No Sage change:** `parse_ytd.py`, `parse_employees.py`, `match.py`, `validate.py`, `generate_003.py` are not modified (only `models.py` gains set entries). All existing tests must pass unchanged.
- **Rulings:** tax year = sheet tab name, month = row position (in-sheet month labels are stale and ignored); UIF is recomputed from earning columns, sheet divergences become soft warnings.
- **`Reistoelaag` stays OUT of every remunerability map** — the existing "unknown earning type" warning must fire if it ever appears.
- **PII:** `List 2.xlsx` / `Copy of List.xlsx` contain real IDs; never commit them (`*.xlsx` is gitignored).
- Environment: Windows / PowerShell. Run tests with `python -m pytest`. Work on branch `standard-format`; commit per task; **never push or merge** (Melton smoke-tests first).

---

### Task 1: openpyxl dependency + format detection

**Files:**
- Modify: `requirements.txt`
- Create: `uif/parse_standard.py`
- Create: `tests/test_parse_standard.py`

**Interfaces:**
- Produces: `parse_standard.detect_format(file_bytes: bytes) -> str` returning `"standard"` (xlsx) or `"sage"` (anything else).

- [ ] **Step 1: Add openpyxl to requirements and install**

`requirements.txt` becomes:

```
streamlit>=1.32
pandas>=2.0
openpyxl>=3.1
```

Run: `pip install -r requirements.txt`

- [ ] **Step 2: Write the failing test**

Create `tests/test_parse_standard.py`:

```python
"""Tests for the Standard Format xlsx parsers."""

from uif import parse_standard


def test_detect_format():
    # xlsx files are zip archives and start with the PK magic.
    assert parse_standard.detect_format(b"PK\x03\x04rest-of-zip") == "standard"
    assert parse_standard.detect_format(b"Employee code:,32\r\n") == "sage"
    assert parse_standard.detect_format(b"") == "sage"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_parse_standard.py -v`
Expected: FAIL — `cannot import name 'parse_standard'`

- [ ] **Step 4: Write minimal implementation**

Create `uif/parse_standard.py`:

```python
"""
Parsers for "Standard Format" xlsx workbooks — hand-kept payroll for clients
not on Sage (first case: the client).

Two workbooks:
  - payroll workbook: one sheet per tax year ("2022".."2027"), each holding
    per-employee identity blocks followed by a 12-row month table;
  - master workbook: an "Employee details" sheet, one row per employee.

Data-quality rulings (docs/superpowers/specs/2026-08-11-standard-format-design.md):
  - tax year comes from the sheet tab name and month from row position; the
    in-sheet month labels are stale template copies and are ignored;
  - UIF is recomputed from the earning columns; months where the sheet's own
    UIF column differs are reported as soft warnings.
"""

from __future__ import annotations


def detect_format(file_bytes: bytes) -> str:
    """'standard' for xlsx (zip magic), 'sage' for anything else (CSV)."""
    return "standard" if file_bytes[:4] == b"PK\x03\x04" else "sage"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_parse_standard.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```powershell
git add requirements.txt uif/parse_standard.py tests/test_parse_standard.py
git commit -m "feat: Standard Format detection + openpyxl dependency"
```

---

### Task 2: Synthetic workbook fixtures + sheet helpers

**Files:**
- Create: `tests/standard_fixtures.py`
- Modify: `uif/parse_standard.py`
- Test: `tests/test_parse_standard.py`

**Interfaces:**
- Produces (fixtures): `build_master_workbook() -> bytes`, `build_payroll_workbook() -> bytes` (year sheets `"2023"` and `"2025"` + a non-year `"Notes"` sheet; employees `001`/`002`), `build_payroll_workbook_missing_month() -> bytes` (11-row block on sheet `"2024"`).
- Produces (module): `list_year_sheets(file_bytes: bytes) -> list[str]`, `tax_year_end_year(sheet_name: str) -> int`, `read_company_header(file_bytes: bytes, sheet_name: str) -> dict[str, str]` with keys `company`, `paye`, `uif`.

- [ ] **Step 1: Create the fixtures module**

Create `tests/standard_fixtures.py`:

```python
"""In-memory builders for synthetic Standard Format workbooks (no PII)."""

from __future__ import annotations

import io
from datetime import datetime

import openpyxl

# Deliberately stale labels (as in the real workbook): wrong years, and row 2
# even carries a wrong month. Parsers must map by row position instead.
STALE_LABELS = [
    "03/2023", "10/2022", "05/2023", "06/2023", "07/2023", "08/2023",
    "09/2023", "10/2023", "11/2023", "12/2023", "01/2024", "02/2024",
]
CORRECT_LABELS_2023 = [
    "03/2022", "04/2022", "05/2022", "06/2022", "07/2022", "08/2022",
    "09/2022", "10/2022", "11/2022", "12/2022", "01/2023", "02/2023",
]

_HEADER = ["", "Salaris", "Leave pay", "Oortyd", "Bonus", "Reistoelaag",
           "Verlof", "Bruto salaris", "PAYE", "SDL", "UIF", "UIF"]


def _month_row(label, salaris=0.0, leave=0.0, oortyd=0.0, bonus=0.0,
               reis=0.0, verlof=0.0, bruto=None, uif1=None):
    total = salaris + leave + oortyd + bonus + reis + verlof
    if bruto is None:
        bruto = total
    if uif1 is None:
        uif1 = round(min(total, 17712.0) * 0.01, 4)
    return [label, salaris, leave, oortyd, bonus, reis, verlof,
            bruto, 0, round(bruto * 0.01, 4), uif1, uif1 * 2]


def _block(ws, nr, name, surname, id_no, start, end, reason, month_rows):
    ws.append(["Employee Nr.:", nr])
    ws.append(["Name:", name])
    ws.append(["Surname:", surname])
    ws.append(["ID No.:", id_no])
    ws.append(["Income Tax Nr.:", "1234567890"])
    ws.append(["Start date:", start])
    ws.append(["End date:", end])
    ws.append(["Reason:", reason])
    ws.append([])
    ws.append(["", "", "", "", "", "", "", "", "", "1%", "1%", "2%"])
    ws.append(_HEADER)
    ws.append([])
    for row in month_rows:
        ws.append(row)
    ws.append([""] + [sum(r[i] for r in month_rows) for i in range(1, 12)])
    ws.append([])


def build_payroll_workbook() -> bytes:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    for sheet_name, labels in (("2023", CORRECT_LABELS_2023), ("2025", STALE_LABELS)):
        ws = wb.create_sheet(sheet_name)
        ws.append(["Company:", "Acme Electrical (Pty) Ltd"])
        ws.append(["Financial year:", 2024])          # stale on purpose
        ws.append(["PAYE No.:", "7012345678"])
        ws.append(["UIF No.:", "0123456/7"])
        ws.append([])

        if sheet_name == "2023":
            emp1_rows = [_month_row(labels[i]) for i in range(11)]
            emp1_rows.append(_month_row(labels[11], salaris=6000.0))          # February
        else:
            emp1_rows = [
                _month_row(labels[0], salaris=10000.0),                       # March: clean
                _month_row(labels[1], salaris=8300.0, uif1=75.00),           # April: UIF divergence
                _month_row(labels[2], salaris=5000.0, bruto=5100.0),          # May: bruto mismatch
                _month_row(labels[3], salaris=20000.0),                       # June: capped, no warning
                *(_month_row(labels[i]) for i in range(4, 9)),
                _month_row(labels[9], salaris=5500.0, leave=5200.0, bonus=4600.0),  # December
                _month_row(labels[10]),
                _month_row(labels[11]),
            ]
        _block(ws, "001", "Petrus Johannes", "Botha", "AB123456",
               "03/09/2018", "N/A", "-", emp1_rows)
        _block(ws, "002", "Piet", "van Wyk", "9103105023081",
               datetime(2018, 4, 3), "05/04/2022", "Death",
               [_month_row(labels[i]) for i in range(12)])

    wb.create_sheet("Notes").append(["scratch", "not a year sheet"])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_payroll_workbook_missing_month() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "2024"
    _block(ws, "001", "Jan", "Marais", "9001015009087",
           "01/02/2020", "N/A", "-",
           [_month_row(f"{m:02d}/2023") for m in range(1, 12)])   # 11 rows
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_master_workbook() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Employee details"
    ws.append(["Employee Number", "Name", "Surname", "ID No. / Passport Number",
               "Date of Birth", "Income Tax No.", "Start Date", "End Date", "Reason"])
    ws.append(["001", "Petrus Johannes", "Botha", "AB123456",
               "14/02/1979", "1234567801", "03/09/2018", "N/A", "-"])
    ws.append(["002", "Daniel Sipho ", "Nkosi", 9103105023081,
               datetime(1991, 3, 10), "1122334455", datetime(2018, 4, 3), "N/A", "-"])
    ws.append(["003", "Andries ", "Fourie", "8807235112083",
               "23/07/1988", "2233445566", "02/03/2015", "07/11/2022", "Death"])
    ws.append(["009", "Willem Karel ", "Van Der Walt", "6512315678087",
               "31/12/1965", "3344556677", "01/07/2019", "N/A", "-"])
    ws.append(["010"])          # number-only stub row — must be skipped
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_parse_standard.py`:

```python
from tests.standard_fixtures import (
    build_master_workbook,
    build_payroll_workbook,
    build_payroll_workbook_missing_month,
)


def test_list_year_sheets_filters_and_sorts():
    assert parse_standard.list_year_sheets(build_payroll_workbook()) == ["2023", "2025"]


def test_tax_year_end_year():
    assert parse_standard.tax_year_end_year("2025") == 2025
    assert parse_standard.tax_year_end_year(" 2023 ") == 2023


def test_read_company_header():
    header = parse_standard.read_company_header(build_payroll_workbook(), "2023")
    assert header == {
        "company": "Acme Electrical (Pty) Ltd",
        "paye": "7012345678",
        "uif": "0123456/7",
    }
```

(If `tests/test_parse_standard.py` complains about the `tests.` import prefix, note the suite already has `tests/__init__.py`, so the package import is valid.)

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_parse_standard.py -v`
Expected: 3 new FAILs — `module 'uif.parse_standard' has no attribute 'list_year_sheets'` etc.

- [ ] **Step 4: Implement the helpers**

In `uif/parse_standard.py`, extend the imports and add:

```python
import io
import re

import openpyxl
```

(keep `from __future__ import annotations` first), then below `detect_format`:

```python
def _load(file_bytes: bytes):
    return openpyxl.load_workbook(
        io.BytesIO(file_bytes), data_only=True, read_only=True
    )


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def list_year_sheets(file_bytes: bytes) -> list[str]:
    """Sheet names that are 4-digit years, sorted ascending."""
    wb = _load(file_bytes)
    try:
        names = [n for n in wb.sheetnames if re.fullmatch(r"\d{4}", n.strip())]
    finally:
        wb.close()
    return sorted(names, key=int)


def tax_year_end_year(sheet_name: str) -> int:
    """Ruling: the sheet tab name IS the tax-year end year."""
    return int(str(sheet_name).strip())


def read_company_header(file_bytes: bytes, sheet_name: str) -> dict[str, str]:
    """Company / PAYE / UIF cells from the top of a payroll year sheet."""
    out = {"company": "", "paye": "", "uif": ""}
    labels = {"Company:": "company", "PAYE No.:": "paye", "UIF No.:": "uif"}
    wb = _load(file_bytes)
    try:
        for row in wb[sheet_name].iter_rows(max_row=8, values_only=True):
            key = labels.get(_text(row[0] if row else None))
            if key and len(row) > 1:
                out[key] = _text(row[1])
    finally:
        wb.close()
    return out
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_parse_standard.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```powershell
git add uif/parse_standard.py tests/standard_fixtures.py tests/test_parse_standard.py
git commit -m "feat: Standard Format sheet helpers + synthetic workbook fixtures"
```

---

### Task 3: Employee master parser

**Files:**
- Modify: `uif/parse_standard.py`
- Test: `tests/test_parse_standard.py`

**Interfaces:**
- Consumes: `build_master_workbook()` fixture; existing `uif.parse_employees.parse_employee_code`, `parse_id_number`, `extract_first_name`; `uif.models.EmployeeRecord`.
- Produces: `parse_standard.parse_employees(file_bytes: bytes) -> dict[str, EmployeeRecord]` (keys are normalised codes: `"001"` → `"1"`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_parse_standard.py`:

```python
import io

import openpyxl
import pytest


def test_parse_employees_reads_master_sheet():
    records = parse_standard.parse_employees(build_master_workbook())
    assert sorted(records) == ["1", "2", "3", "9"]   # stub row 010 skipped

    botha = records["1"]
    assert botha.first_names == "Petrus"
    assert botha.surname == "Botha"
    assert botha.id_number == ""                      # not 13 digits
    assert botha.passport_number == "AB123456"
    assert botha.date_of_birth == "19790214"
    assert botha.date_engaged == "20180903"
    assert botha.end_date == ""
    assert botha.employee_status == "Normal"
    assert botha.uif_status == "Contributes"

    nkosi = records["2"]     # numeric ID cell + Excel datetime cells
    assert nkosi.id_number == "9103105023081"
    assert nkosi.passport_number == ""
    assert nkosi.date_of_birth == "19910310"
    assert nkosi.date_engaged == "20180403"

    fourie = records["3"]    # terminated
    assert fourie.end_date == "20221107"
    assert fourie.employee_status == "Terminated"

    vdwalt = records["9"]    # multi-word surname column survives whole
    assert vdwalt.surname == "Van Der Walt"
    assert vdwalt.first_names == "Willem"


def test_parse_employees_requires_master_sheet():
    wb = openpyxl.Workbook()
    wb.active.title = "Wrong name"
    buf = io.BytesIO()
    wb.save(buf)
    with pytest.raises(ValueError, match="Employee details"):
        parse_standard.parse_employees(buf.getvalue())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_parse_standard.py -v`
Expected: 2 new FAILs — no attribute `parse_employees`

- [ ] **Step 3: Implement**

In `uif/parse_standard.py` add to imports:

```python
import datetime as _dt

from .models import EmployeeRecord
from .parse_employees import extract_first_name, parse_employee_code, parse_id_number
```

Add module constants near the top and the parser:

```python
MASTER_SHEET = "Employee details"
_EMPTY_VALUES = {"", "n/a", "-"}


def _date(value) -> str:
    """Cell to YYYYMMDD. Accepts Excel datetimes and 'DD/MM/YYYY' strings;
    'N/A', '-' and blank mean no date."""
    if isinstance(value, (_dt.datetime, _dt.date)):
        return f"{value:%Y%m%d}"
    text = _text(value)
    if text.lower() in _EMPTY_VALUES:
        return ""
    match = re.search(r"(\d{2})/(\d{2})/(\d{4})", text)
    return f"{match.group(3)}{match.group(2)}{match.group(1)}" if match else ""


def parse_employees(file_bytes: bytes) -> dict[str, EmployeeRecord]:
    """Parse the master workbook's 'Employee details' sheet."""
    wb = _load(file_bytes)
    try:
        if MASTER_SHEET not in wb.sheetnames:
            raise ValueError(
                f'Could not find the "{MASTER_SHEET}" sheet in the employee '
                f"master workbook."
            )
        rows = list(wb[MASTER_SHEET].iter_rows(values_only=True))
    finally:
        wb.close()
    if not rows:
        raise ValueError(f'The "{MASTER_SHEET}" sheet is empty.')

    header = [_text(c).lower() for c in rows[0]]

    def find_col(prefix: str) -> int | None:
        for i, cell in enumerate(header):
            if cell.startswith(prefix):
                return i
        return None

    cols = {
        "code": find_col("employee number"),
        "name": find_col("name"),
        "surname": find_col("surname"),
        "id": find_col("id no"),
        "dob": find_col("date of birth"),
        "start": find_col("start date"),
        "end": find_col("end date"),
    }
    missing = [k for k in ("code", "name", "surname", "id") if cols[k] is None]
    if missing:
        raise ValueError(
            f'The "{MASTER_SHEET}" sheet is missing expected columns: '
            f"{', '.join(sorted(missing))}."
        )

    def cell(row, key):
        i = cols[key]
        return row[i] if i is not None and i < len(row) else None

    records: dict[str, EmployeeRecord] = {}
    for row in rows[1:]:
        code = parse_employee_code(cell(row, "code"))
        first = extract_first_name(_text(cell(row, "name")))
        surname = _text(cell(row, "surname"))
        if not code or (not first and not surname):
            continue  # stub rows: an employee number with no identity yet

        raw_id = _text(cell(row, "id"))
        digits = parse_id_number(raw_id)
        if len(digits) == 13 and digits.isdigit():
            id_number, passport = digits, ""
        else:
            id_number = ""
            passport = "" if raw_id.lower() in _EMPTY_VALUES else raw_id

        end_date = _date(cell(row, "end"))
        records[code] = EmployeeRecord(
            employee_code=code,
            surname=surname,
            first_names=first,
            id_number=id_number,
            passport_number=passport,
            date_of_birth=_date(cell(row, "dob")),
            date_engaged=_date(cell(row, "start")),
            end_date=end_date,
            employee_status="Terminated" if end_date else "Normal",
            uif_status="Contributes",
        )
    return records
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_parse_standard.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```powershell
git add uif/parse_standard.py tests/test_parse_standard.py
git commit -m "feat: Standard Format employee master parser"
```

---

### Task 4: Payroll workbook parser

**Files:**
- Modify: `uif/parse_standard.py`
- Test: `tests/test_parse_standard.py`

**Interfaces:**
- Consumes: fixtures from Task 2; `uif.models.TAX_YEAR_MONTHS`, `UIF_REMUNERATION_CAP`, `YtdRecord`.
- Produces: `parse_standard.parse_ytd(file_bytes: bytes, sheet_name: str) -> tuple[dict[str, YtdRecord], list[str]]` — records keyed on normalised code, plus soft-warning strings. `EARNING_COLUMNS` tuple constant.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_parse_standard.py`:

```python
def test_parse_ytd_maps_months_by_position_not_label():
    records, _ = parse_standard.parse_ytd(build_payroll_workbook(), "2025")
    rec = records["1"]
    # Row 2 is labelled "10/2022" (stale) but is positionally April.
    assert rec.gross("April") == 8300.0
    assert rec.earnings["March"] == {"Salaris": 10000.0}
    assert rec.earnings["December"] == {
        "Salaris": 5500.0, "Leave pay": 5200.0, "Bonus": 4600.0,
    }
    assert rec.gross("December") == 15300.0
    assert rec.employee_name == "Petrus Johannes Botha"
    assert rec.status == "Employed"
    assert rec.end_date == ""


def test_parse_ytd_termination_and_death_warning():
    records, warnings = parse_standard.parse_ytd(build_payroll_workbook(), "2025")
    rec = records["2"]
    assert rec.status == "Terminated"
    assert rec.end_date == "20220405"
    assert any("Death" in w and "status 06" in w for w in warnings)


def test_parse_ytd_integrity_warnings():
    _, warnings = parse_standard.parse_ytd(build_payroll_workbook(), "2025")
    assert any("75.00" in w and "April" in w for w in warnings)         # UIF divergence
    assert any("Bruto salaris" in w and "May" in w for w in warnings)   # bruto mismatch
    assert not any("June" in w for w in warnings)                       # cap != divergence


def test_parse_ytd_rejects_wrong_month_count():
    with pytest.raises(ValueError, match="expected 12"):
        parse_standard.parse_ytd(build_payroll_workbook_missing_month(), "2024")


def test_parse_ytd_unknown_sheet():
    with pytest.raises(ValueError, match="2031"):
        parse_standard.parse_ytd(build_payroll_workbook(), "2031")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_parse_standard.py -v`
Expected: 5 new FAILs — no attribute `parse_ytd`

- [ ] **Step 3: Implement**

In `uif/parse_standard.py`, extend the models import to:

```python
from .models import TAX_YEAR_MONTHS, UIF_REMUNERATION_CAP, EmployeeRecord, YtdRecord
```

Add constants and helpers near `MASTER_SHEET`:

```python
EARNING_COLUMNS = ("Salaris", "Leave pay", "Oortyd", "Bonus", "Reistoelaag", "Verlof")
_MONTH_LABEL_RE = re.compile(r"\d{2}/\d{4}")


def _num(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace("\xa0", "").replace(" ", "").replace(",", "").strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0
```

Add the parser:

```python
def parse_ytd(
    file_bytes: bytes, sheet_name: str
) -> tuple[dict[str, YtdRecord], list[str]]:
    """
    Parse one year sheet of the payroll workbook into
    ({employee_code: YtdRecord}, soft_warnings).

    Months map by row position (1st table row = March .. 12th = February);
    the MM/YYYY labels are stale template copies and only gate which rows
    count as month rows. A block without exactly 12 month rows is a
    blocking parse error.
    """
    wb = _load(file_bytes)
    try:
        if sheet_name not in wb.sheetnames:
            raise ValueError(
                f"Sheet '{sheet_name}' was not found in the payroll workbook."
            )
        rows = list(wb[sheet_name].iter_rows(values_only=True))
    finally:
        wb.close()

    records: dict[str, YtdRecord] = {}
    warnings: list[str] = []

    current: YtdRecord | None = None
    name_part = surname_part = ""
    earn_cols: dict[int, str] = {}
    bruto_col: int | None = None
    uif1_col: int | None = None
    month_index = 0

    def finalise() -> None:
        if current is not None and month_index != 12:
            raise ValueError(
                f"Employee {current.employee_code} ({current.employee_name}) "
                f"on sheet '{sheet_name}' has {month_index} month rows, "
                f"expected 12."
            )

    for row in rows:
        first = _text(row[0] if row else None)

        if first == "Employee Nr.:":
            finalise()
            code = parse_employee_code(row[1] if len(row) > 1 else None)
            current = YtdRecord(
                employee_code=code,
                employee_name="",
                status="Employed",
                earnings={m: {} for m in TAX_YEAR_MONTHS},
            )
            records[code] = current
            name_part = surname_part = ""
            earn_cols, bruto_col, uif1_col = {}, None, None
            month_index = 0
            continue
        if current is None:
            continue

        value = _text(row[1]) if len(row) > 1 else ""
        if first == "Name:":
            name_part = value
            current.employee_name = f"{name_part} {surname_part}".strip()
            continue
        if first == "Surname:":
            surname_part = value
            current.employee_name = f"{name_part} {surname_part}".strip()
            continue
        if first == "End date:":
            current.end_date = _date(row[1] if len(row) > 1 else None)
            if current.end_date:
                current.status = "Terminated"
            continue
        if first == "Reason:":
            if value.lower() == "death":
                warnings.append(
                    f"Employee {current.employee_code} "
                    f"({current.employee_name}): reason is 'Death' — the "
                    f"declaration uses status 06, the same as any other "
                    f"termination."
                )
            continue

        cells = [_text(c) for c in row]
        if "Salaris" in cells and "Bruto salaris" in cells:
            earn_cols = {i: c for i, c in enumerate(cells) if c in EARNING_COLUMNS}
            bruto_col = cells.index("Bruto salaris")
            uif_positions = [i for i, c in enumerate(cells) if c == "UIF"]
            uif1_col = uif_positions[0] if uif_positions else None
            continue

        if earn_cols and _MONTH_LABEL_RE.fullmatch(first):
            month_index += 1
            if month_index > 12:
                continue  # finalise() reports the bad count
            month = TAX_YEAR_MONTHS[month_index - 1]

            row_total = 0.0
            for i, earning_name in earn_cols.items():
                amount = _num(row[i]) if i < len(row) else 0.0
                row_total += amount
                if amount:
                    current.earnings[month][earning_name] = (
                        current.earnings[month].get(earning_name, 0.0) + amount
                    )

            label = (
                f"Employee {current.employee_code} "
                f"({current.employee_name}), {month}"
            )
            if bruto_col is not None and bruto_col < len(row):
                bruto = _num(row[bruto_col])
                if abs(bruto - row_total) > 0.01:
                    warnings.append(
                        f"{label}: the sheet's Bruto salaris ({bruto:.2f}) "
                        f"does not equal the sum of the earning columns "
                        f"({row_total:.2f})."
                    )
            if uif1_col is not None and uif1_col < len(row):
                sheet_uif = _num(row[uif1_col])
                expected = min(row_total, UIF_REMUNERATION_CAP) * 0.01
                if abs(sheet_uif - expected) > 0.02:
                    warnings.append(
                        f"{label}: the sheet's UIF column ({sheet_uif:.2f}) "
                        f"is not 1% of the (capped) earnings "
                        f"({expected:.2f}) — the app uses the recomputed "
                        f"value."
                    )

    finalise()
    return records, warnings
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_parse_standard.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```powershell
git add uif/parse_standard.py tests/test_parse_standard.py
git commit -m "feat: Standard Format payroll parser with integrity warnings"
```

---

### Task 5: Confirm Standard earning names in models

**Files:**
- Modify: `uif/models.py:51-54`
- Test: `tests/test_parse_standard.py`

**Interfaces:**
- Produces: `"Salaris"`, `"Leave pay"`, `"Oortyd"`, `"Bonus"`, `"Verlof"` in `CONFIRMED_FULL_REMUNERABLE`; `"Reistoelaag"` in neither map.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_parse_standard.py`:

```python
from uif.models import CONFIRMED_FULL_REMUNERABLE, REMUNERABLE_PCT


def test_standard_earning_names_are_confirmed_remunerable():
    for name in ("Salaris", "Leave pay", "Oortyd", "Bonus", "Verlof"):
        assert name in CONFIRMED_FULL_REMUNERABLE
    # Reistoelaag stays unknown on purpose: the existing "unknown earning
    # type" soft warning must fire if it ever carries a value.
    assert "Reistoelaag" not in CONFIRMED_FULL_REMUNERABLE
    assert "Reistoelaag" not in REMUNERABLE_PCT
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_parse_standard.py::test_standard_earning_names_are_confirmed_remunerable -v`
Expected: FAIL — `'Salaris' in CONFIRMED_FULL_REMUNERABLE` is false

- [ ] **Step 3: Implement**

In `uif/models.py`, replace the `CONFIRMED_FULL_REMUNERABLE` set with:

```python
CONFIRMED_FULL_REMUNERABLE = {
    "Basic salary", "Overtime 1.5", "Overtime 2.0", "Bonus",
    "Honey Bonus - Haygrove", "Pollination Bonus", "Back pay normal time",
    # Standard Format (xlsx) earning columns. "Reistoelaag" is deliberately
    # absent so the unknown-earning-type warning fires if it ever appears.
    "Salaris", "Leave pay", "Oortyd", "Verlof",
}
```

(`"Bonus"` is already present.)

- [ ] **Step 4: Run the full suite to verify nothing broke**

Run: `python -m pytest -v`
Expected: all PASS (existing Sage tests included)

- [ ] **Step 5: Commit**

```powershell
git add uif/models.py tests/test_parse_standard.py
git commit -m "feat: confirm Standard Format earning names as fully remunerable"
```

---

### Task 6: Integration test through the untouched pipeline

**Files:**
- Test: `tests/test_parse_standard.py`

**Interfaces:**
- Consumes: everything above; existing `uif.match.join`, `uif.validate.validate`, `uif.generate_003.build`, `uif.models.Company`.

- [ ] **Step 1: Write the test**

Append to `tests/test_parse_standard.py`:

```python
from uif import generate_003, match, validate
from uif.models import Company


def test_standard_pair_through_existing_pipeline():
    ytd, _ = parse_standard.parse_ytd(build_payroll_workbook(), "2023")
    employees = parse_standard.parse_employees(build_master_workbook())
    matched, _ = match.join(ytd, employees)

    blocking, _ = validate.validate(matched, "February")
    assert blocking == []

    company = Company(
        uif_ref="012345678",
        paye_ref="7777777777",
        contact_name="Tester",
        contact_phone="0123456789",
        contact_email_header="tax@example.test",
        contact_email_footer="tax@example.test",
    )
    content = generate_003.build(matched, "February", "202302", company)
    lines = content.decode("latin-1").split("\r\n")

    assert lines[0].startswith('8000,"UICR"')
    assert "8070,202302" in lines[0]
    worker = lines[1]                          # only emp 001 earned in February
    assert '8210,"AB123456"' in worker        # passport, quoted
    assert '8230,"Botha"' in worker
    assert "8280,01" in worker
    assert "8300,6000,8310,6000,8320,120" in worker
    footer = lines[2]
    assert footer.startswith('8002,"UIEM"')
    assert "8150,1" in footer
```

- [ ] **Step 2: Run the test — it should pass immediately**

Run: `python -m pytest tests/test_parse_standard.py::test_standard_pair_through_existing_pipeline -v`
Expected: PASS. If it fails, the bug is in Tasks 3–5 — fix there, not in the Sage pipeline modules (which this plan must not touch).

- [ ] **Step 3: Commit**

```powershell
git add tests/test_parse_standard.py
git commit -m "test: Standard Format pair generates a declaration through the existing pipeline"
```

---

### Task 7: Streamlit wiring (dispatch, year picker, header hint)

**Files:**
- Modify: `streamlit_app.py:15` (imports), `:226-234` (cached parsers), `:252-284` (upload section), `:288-301` (parse + dispatch), `:313-314` (warnings)
- Modify: `README.md:10-27` (How it works)

**Interfaces:**
- Consumes: every `parse_standard` function above (exact signatures in Tasks 1–4).

- [ ] **Step 1: Update the import and cached parsers**

In `streamlit_app.py` change the `uif` import to:

```python
from uif import generate_003, match, parse_employees, parse_standard, parse_ytd, validate
```

Below the existing `_parse_employees` cache function add:

```python
@st.cache_data(show_spinner=False)
def _list_year_sheets(data: bytes):
    return parse_standard.list_year_sheets(data)


@st.cache_data(show_spinner=False)
def _parse_standard_ytd(data: bytes, sheet: str):
    return parse_standard.parse_ytd(data, sheet)


@st.cache_data(show_spinner=False)
def _parse_standard_employees(data: bytes):
    return parse_standard.parse_employees(data)
```

- [ ] **Step 2: Update the upload section**

Replace the section header call and intro markdown (currently "Drop in the Sage exports" and the column-B paragraph) with:

```python
section("Step 1", "Drop in the payroll files")

st.markdown(
    "Both files must be for the **same company and same tax year**. Two "
    "formats are supported and detected automatically, per file: the Sage "
    "CSV exports, and Standard Format workbooks (.xlsx). For a **Sage "
    "Employee Details CSV** only: open it in Excel first, format column B as "
    "**Number** with 0 decimals, and save. That stops Excel mangling SA ID "
    "numbers into scientific notation."
)
```

Change both uploaders to accept xlsx:

```python
with col1:
    ytd_file = st.file_uploader(
        "Year to Date Detail",
        type=["csv", "xlsx"],
        key="ytd_upload",
        help="Sage 'Year to Date Detail' CSV, or a Standard Format payroll "
             "workbook (.xlsx) with one sheet per tax year.",
    )
with col2:
    emp_file = st.file_uploader(
        "Employee Details",
        type=["csv", "xlsx"],
        key="emp_upload",
        help="Sage 'Employee Details' CSV, or the Standard Format employee "
             "master workbook (.xlsx) with an 'Employee details' sheet.",
    )
```

- [ ] **Step 3: Replace the parse + match block with per-file dispatch**

Replace the two existing `try:` parse blocks (between the `# Parse + match` banner and `matched, match_warnings = match.join(...)`) with:

```python
ytd_bytes = ytd_file.getvalue()
emp_bytes = emp_file.getvalue()
standard_warnings: list[str] = []

try:
    if parse_standard.detect_format(ytd_bytes) == "standard":
        year_sheets = _list_year_sheets(ytd_bytes)
        if not year_sheets:
            st.error(
                "This workbook has no year sheets (tabs named like '2025'). "
                "Is it the payroll workbook?"
            )
            st.stop()
        if len(year_sheets) > 1:
            sheet = st.selectbox(
                "Tax year ending February …",
                year_sheets,
                index=len(year_sheets) - 1,
                key="std_year_sheet",
            )
        else:
            sheet = year_sheets[0]
        ytd_data, standard_warnings = _parse_standard_ytd(ytd_bytes, sheet)
        tax_year_end = parse_standard.tax_year_end_year(sheet)
        hint = parse_standard.read_company_header(ytd_bytes, sheet)
        hint_bits = [
            part for part in (
                hint["company"],
                f"PAYE {hint['paye']}" if hint["paye"] else "",
                f"UIF {hint['uif']}" if hint["uif"] else "",
            ) if part
        ]
        if hint_bits:
            st.markdown(
                f"<p style='color:var(--text-muted);'>Workbook header: "
                f"{' · '.join(hint_bits)}. Enter the official reference "
                f"numbers below; nothing is auto-filled.</p>",
                unsafe_allow_html=True,
            )
    else:
        ytd_data, tax_year_end = _parse_ytd(ytd_bytes)
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not read the payroll file: {exc}")
    st.stop()

try:
    if parse_standard.detect_format(emp_bytes) == "standard":
        emp_data = _parse_standard_employees(emp_bytes)
    else:
        emp_data = _parse_employees(emp_bytes)
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not read the employee details file: {exc}")
    st.stop()
```

After the existing `for warning in match_warnings:` loop, add:

```python
for warning in standard_warnings:
    st.warning(warning)
```

- [ ] **Step 4: Update README**

In `README.md`, replace the two numbered upload steps (1 and 2 of "How it works") with:

```markdown
1. Upload the payroll file: the Sage **Year to Date Detail** CSV, or a
   **Standard Format** payroll workbook (.xlsx, one sheet per tax year —
   pick the tax year in the app).
2. Upload the employee master: the Sage **Employee Details** CSV, or the
   Standard Format master workbook (.xlsx, "Employee details" sheet).
   Formats are detected automatically, per file, and may be mixed.
   Sage CSV only: before uploading, open the Employee Details file in
   Excel, format column B as **Number** with 0 decimals, and save —
   otherwise Excel mangles SA ID numbers into scientific notation.
```

- [ ] **Step 5: Run the full suite + import smoke check**

Run: `python -m pytest -v`
Expected: all PASS

Run: `python -c "import ast; ast.parse(open('streamlit_app.py', encoding='utf-8').read()); print('syntax ok')"`
Expected: `syntax ok`

- [ ] **Step 6: Commit**

```powershell
git add streamlit_app.py README.md
git commit -m "feat: per-file format dispatch, tax-year picker, workbook header hint"
```

---

### Task 8: PII hygiene, private regression test, docs

**Files:**
- Move: `List 2.xlsx` → `samples/private/standard_payroll.xlsx`; `Copy of List.xlsx` → `samples/private/standard_master.xlsx`
- Create: `tests/test_standard_regression.py`
- Modify: `samples/README.md`, `PROGRESS.md`

**Interfaces:**
- Consumes: `parse_standard.parse_employees` / `parse_ytd` (Tasks 3–4).

- [ ] **Step 1: Move the real workbooks out of the repo root**

```powershell
New-Item -ItemType Directory -Force samples\private
Move-Item "List 2.xlsx" samples\private\standard_payroll.xlsx
Move-Item "Copy of List.xlsx" samples\private\standard_master.xlsx
git status --short
```

Expected: `git status` shows no xlsx anywhere (`samples/private/` and `*.xlsx` are both gitignored).

Then create `samples/private/standard_expected.json` holding the expected
values read from the real workbooks: employee codes, employee 1's passport
and date of birth, employee 9's surname, the known 2025 monthly figures,
the UIF-divergence fragment, the year-sheet list, and the per-sheet
employee count. It lives in the gitignored `samples/private/`, so real
values never enter the repo — the regression test loads them from this
sidecar and holds no literals of its own.

- [ ] **Step 2: Write the regression test**

Create `tests/test_standard_regression.py`:

```python
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
```

- [ ] **Step 3: Run the regression tests**

Run: `python -m pytest tests/test_standard_regression.py -v`
Expected: 4 PASS (files are present locally). If a figure assertion fails, verify against the workbook before touching parser code — the sidecar values were read from the real file on 2026-08-11.

- [ ] **Step 4: Document the private samples**

In `samples/README.md`, after the Sage filename list, add:

```markdown
    samples/private/standard_payroll.xlsx   Standard Format payroll workbook (one sheet per tax year)
    samples/private/standard_master.xlsx    Standard Format employee master ("Employee details" sheet)

`tests/test_standard_regression.py` uses the two Standard Format workbooks
the same way: it skips automatically when they are absent.
```

- [ ] **Step 5: Update PROGRESS.md**

Append to `PROGRESS.md`:

```markdown
## Step 4 — Standard Format input
Status: **awaiting smoke test** (branch `standard-format`)
Design: `docs/superpowers/specs/2026-08-11-standard-format-design.md`
- New `uif/parse_standard.py`: format detection (zip magic), employee master
  parser ("Employee details" sheet), payroll parser (one sheet per tax year).
- Rulings baked in: tax year from the sheet tab name + month from row
  position (in-sheet labels are stale); UIF recomputed from earning columns
  with soft warnings where the sheet's own UIF column differs.
- Per-file dispatch in the app: Sage CSV and Standard xlsx can be mixed.
  Tax-year selectbox for multi-year workbooks; workbook header shown as a
  hint, never auto-filled.
- `Salaris`/`Leave pay`/`Oortyd`/`Verlof` confirmed fully remunerable;
  `Reistoelaag` deliberately left unknown (warning fires if it appears).
- Real workbooks moved to `samples/private/standard_*.xlsx` (gitignored);
  synthetic-fixture unit tests + private regression tests added.
- Sage pipeline and generation rules untouched; all prior tests pass.
```

- [ ] **Step 6: Full suite, then commit**

Run: `python -m pytest -v`
Expected: everything PASSES (regression tests included, since the files are present).

```powershell
git add tests/test_standard_regression.py samples/README.md PROGRESS.md
git commit -m "test: private regression suite for Standard Format; docs + PII hygiene"
git status --short
```

Expected: clean status, no xlsx tracked.
