"""Shared data structures and constants for the UIF declaration pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field

# Tax-year month order: South African tax year runs March -> February.
TAX_YEAR_MONTHS = [
    "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December", "January", "February",
]

# Calendar month number for each month name.
MONTH_NUMBER = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11,
    "December": 12,
}


def period_code(month_name: str, tax_year_end_year: int) -> str:
    """
    YYYYMM string for field 8070.

    The tax year ends in February of `tax_year_end_year`, so January and
    February fall in that year and March-December in the year before.
    """
    month = MONTH_NUMBER[month_name]
    year = tax_year_end_year if month_name in ("January", "February") else tax_year_end_year - 1
    return f"{year}{month:02d}"

# UIF remunerable earnings are capped at this amount per month.
UIF_REMUNERATION_CAP = 17712.00

# UIF contribution rate per side (employee 1% + employer 1%).
UIF_RATE_PER_SIDE = 0.01

# Fraction of an earning line item that counts towards UIF remuneration.
# Anything not listed here is treated as 100% remunerable.
REMUNERABLE_PCT = {
    "Travel allowance - 80%": 0.80,
    # Severance pay is a voluntary / loss-of-employment award and is explicitly
    # excluded from the UIF definition of remuneration.
    "Severance Pay": 0.00,
}
DEFAULT_REMUNERABLE_PCT = 1.00

# Earning types seen in real exports and confirmed (or safely assumed) to be
# fully UIF-remunerable. An earning type that is in neither this set nor
# REMUNERABLE_PCT triggers a soft warning so the assumption can be verified.
CONFIRMED_FULL_REMUNERABLE = {
    "Basic salary", "Overtime 1.5", "Overtime 2.0", "Bonus",
    "Honey Bonus - Haygrove", "Pollination Bonus", "Back pay normal time",
    # Standard Format (xlsx) earning columns. "Reistoelaag" is deliberately
    # absent so the unknown-earning-type warning fires if it ever appears.
    "Salaris", "Leave pay", "Oortyd", "Verlof",
}

# Sage employee-status text -> SARS .003 status code (field 8280).
STATUS_CODE = {
    "Employed": "01",
    "New": "01",
    "Normal": "01",
    "No longer employed": "06",
    "Terminated": "06",
}
DEFAULT_STATUS_CODE = "01"
TERMINATED_STATUSES = {"No longer employed", "Terminated"}

# Field 8280 — the complete employment status list from E03 spec §8.
# Note 18 is absent from the spec's own table; the jump from 17 to 19 is
# theirs, not a transcription slip.
EMPLOYMENT_STATUS_CODES = {
    "01": "Active",
    "02": "Deceased",
    "03": "Retired",
    "04": "Dismissed",
    "05": "Contract Expired",
    "06": "Resigned",
    "07": "Constructively Dismissed",
    "08": "Employers Insolvency",
    "09": "Maternity / Adoption leave",
    "10": "Illness leave",
    "11": "Retrenched",
    "12": "Transfer to another branch",
    "13": "Absconded",
    "14": "Business Closed",
    "15": "Death of Domestic employer",
    "16": "Voluntary Severance Package",
    "17": "Reduced Working Time",
    "19": "Parental Leave",
}

# Statuses for which spec §9 expects NO 8270 date ("the date employed to is
# valid, and field 8280 is 01, 09 or 10" is a warning).
STATUSES_WITHOUT_END_DATE = {"01", "09", "10"}

# Field 8290 — reason for non-contribution, required whenever 8320 is zero.
NON_CONTRIBUTION_CODES = {
    "01": "Temporary employees (less than 24 hours per month)",
    "02": "Learners in terms of the skills development act",
    "03": "Employees in the national and provincial spheres of government",
    "04": "Employees who are repatriated at the end of their contract of service",
    "05": "Employees who earn commission only",
    "06": "No income paid for the payroll period",
}
DEFAULT_NON_CONTRIBUTION_CODE = "06"

# Declared field lengths from the spec §7 record layouts. Values longer than
# these are truncated on output rather than risking a rejected record.
FIELD_LENGTHS = {
    "8040": 30,   # Contact Person
    "8050": 16,   # Contact Telephone Number
    "8060": 50,   # Contact E-mail Address
    "8210": 16,   # Other Number
    "8220": 25,   # Alternate Number
    "8230": 120,  # Surname
    "8240": 90,   # First Names
    "8160": 50,   # Employer's Email address
}


@dataclass
class Company:
    """One-off company / filer configuration captured from the UI form."""

    uif_ref: str                # 8020 / 8110 / 8115
    paye_ref: str               # 8120
    contact_name: str           # 8040
    contact_phone: str          # 8050
    contact_email_header: str   # 8060
    contact_email_footer: str   # 8160
    submission_mode: str = "LIVE"   # 8030 ("LIVE" or "TEST")


@dataclass
class YtdRecord:
    """One employee's Year to Date Detail block."""

    employee_code: str
    employee_name: str
    status: str                  # "Employed" / "New" / "No longer employed"
    end_date: str = ""           # "To:" date from the status line, YYYYMMDD
    # month name -> {earning line-item name -> amount}
    earnings: dict[str, dict[str, float]] = field(default_factory=dict)

    def gross(self, month: str) -> float:
        """Total earnings for the given month."""
        return round(sum(self.earnings.get(month, {}).values()), 2)

    def remunerable(self, month: str) -> float:
        """UIF-remunerable earnings for the month (pre-cap)."""
        total = 0.0
        for name, amount in self.earnings.get(month, {}).items():
            pct = REMUNERABLE_PCT.get(name, DEFAULT_REMUNERABLE_PCT)
            total += amount * pct
        return round(total, 2)


@dataclass
class EmployeeRecord:
    """One employee's identity block from the Employee Details report."""

    employee_code: str
    surname: str                 # 8230
    first_names: str             # 8240
    id_number: str               # 8200 (13 digits) — "" if none
    passport_number: str         # 8210 — "" if none
    date_of_birth: str           # 8250, YYYYMMDD
    date_engaged: str            # 8260, YYYYMMDD
    end_date: str                # 8270, YYYYMMDD — "" if not terminated
    employee_status: str         # "Normal" / "Terminated"
    uif_status: str              # "Contributes" / "Excluded" / ...


@dataclass
class MatchedRecord:
    """An employee joined across both reports on employee code."""

    employee_code: str
    employee: EmployeeRecord | None
    ytd: YtdRecord | None

    @property
    def in_ytd(self) -> bool:
        return self.ytd is not None

    @property
    def in_employees(self) -> bool:
        return self.employee is not None
