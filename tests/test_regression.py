"""
Regression tests against real Sage exports.

These run only when real files are present in ``samples/private/`` (a gitignored
folder that never leaves the maintainer's machine). They are skipped otherwise,
so CI and a fresh clone stay green without any PII in the repo.

Expected files (any subset may be present):
    samples/private/ytd_2024.csv         (Year to Date Detail, tax year 2024)
    samples/private/employees_2024.csv   (Employee Details, tax year 2024)
    samples/private/expected_2024.003    (the real Sage .003, period 202402)
    samples/private/ytd_2025.csv         (Year to Date Detail, tax year 2025)
    samples/private/employees_2025.csv   (Employee Details, tax year 2025)
    samples/private/expected_2025.004    (the real Sage .004, period 202502)

The comparison is structural: for every employee the app places in a month's
file, that employee must appear in the real Sage file with identical 8300 /
8310 / 8320 values. This sidesteps line ordering and the known 2024 catch-up
record (Kwepile), while still proving the figures and inclusion logic.
"""

from pathlib import Path

import pytest

from uif import generate_003, match, parse_employees, parse_ytd
from uif.models import Company

PRIVATE = Path(__file__).resolve().parent.parent / "samples" / "private"


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def _parse_declaration(raw: bytes) -> list[dict[str, str]]:
    """Parse a .003/.004 file into a list of {field_code: value} dicts."""
    records = []
    for line in _decode(raw).splitlines():
        if not line.strip():
            continue
        parts = line.split(",")
        record = {}
        i = 0
        while i + 1 < len(parts):
            code = parts[i].strip()
            value = parts[i + 1].strip().strip('"')
            record[code] = value
            i += 2
        records.append(record)
    return records


def _company_from_header(declaration: list[dict[str, str]]) -> Company:
    header = declaration[0]
    footer = declaration[-1]
    return Company(
        uif_ref=header["8020"],
        paye_ref=footer.get("8120", ""),
        contact_name=header.get("8040", ""),
        contact_phone=header.get("8050", ""),
        contact_email_header=header.get("8060", ""),
        contact_email_footer=footer.get("8160", header.get("8060", "")),
        submission_mode=header.get("8030", "LIVE"),
    )


def _figures_by_identity(declaration: list[dict[str, str]]) -> dict[str, tuple]:
    """Map each UIWK record's ID/passport to (8300, 8310, 8320)."""
    out = {}
    for record in declaration:
        if record.get("8001") != "UIWK":
            continue
        identity = record.get("8200") or record.get("8210")
        out[identity] = (record["8300"], record["8310"], record["8320"])
    return out


def _run_year(ytd_name: str, emp_name: str, expected_name: str) -> None:
    ytd_path = PRIVATE / ytd_name
    emp_path = PRIVATE / emp_name
    expected_path = PRIVATE / expected_name
    if not (ytd_path.exists() and emp_path.exists() and expected_path.exists()):
        pytest.skip(f"real samples not present ({ytd_name} / {emp_name} / {expected_name})")

    ytd_bytes = ytd_path.read_bytes()
    ytd_data, _ = parse_ytd.parse(ytd_bytes)
    emp_data = parse_employees.parse(emp_path.read_bytes())
    matched, _ = match.join(ytd_data, emp_data)

    real = _parse_declaration(expected_path.read_bytes())
    company = _company_from_header(real)
    real_figures = _figures_by_identity(real)

    generated = _parse_declaration(
        generate_003.build(matched, "February", real[0]["8070"], company)
    )
    generated_figures = _figures_by_identity(generated)

    assert generated_figures, "the app generated no UIWK records"
    for identity, figures in generated_figures.items():
        assert identity in real_figures, f"{identity} is not in the real Sage file"
        assert figures == real_figures[identity], (
            f"{identity}: app produced 8300/8310/8320 {figures}, "
            f"Sage file has {real_figures[identity]}"
        )


def test_2024_february_figures_match_real_003():
    _run_year("ytd_2024.csv", "employees_2024.csv", "expected_2024.003")


def test_2025_february_figures_match_real_004():
    _run_year("ytd_2025.csv", "employees_2025.csv", "expected_2025.004")
