"""Tests for the UI-19 row rules (ported from the standalone UI19 script)."""

from uif import ui19
from uif.models import EmployeeRecord, YtdRecord

PERIOD = "202505"


def ytd(code="1", name="Jane Sample", earnings=None, uif=None, start="", end="", status="Employed"):
    return YtdRecord(
        employee_code=code, employee_name=name, status=status, end_date=end,
        earnings={"May": earnings if earnings is not None else {"Basic salary": 5000.0}},
        start_date=start, uif_deducted=uif if uif is not None else {"May": 50.0},
    )


def emp(code="1", **kw):
    base = dict(
        employee_code=code, surname="Sample", first_names="Jane", id_number="8306056177085",
        passport_number="", date_of_birth="19830605", date_engaged="20200101", end_date="",
        employee_status="Normal", uif_status="Contributes", employee_name="Ms J Sample",
        full_names="Jane", average_hours=173.33,
    )
    base.update(kw)
    return EmployeeRecord(**base)


def test_names_follow_script_helpers():
    assert ui19.split_employee_detail_name("Ms E Smart") == ("Smart", "E.")
    assert ui19.split_employee_detail_name("Mr JP Van de Rheede") == ("Van de Rheede", "J.P.")
    assert ui19.split_employee_detail_name("Mt N Langeni") == ("Langeni", "N.")
    assert ui19.split_full_name("Leethan Van de Rheede") == ("Van de Rheede", "L.")
    assert ui19.initials_from_first_names("Petrus Johannes") == "P.J."


def test_name_source_precedence():
    rows, _ = ui19.form_rows({"1": ytd()}, {"1": emp()}, "May", PERIOD)
    assert (rows[0].surname, rows[0].initials) == ("Sample", "J.")
    standard = emp(employee_name="", surname="Botha", full_names="Petrus Johannes")
    rows, _ = ui19.form_rows({"1": ytd()}, {"1": standard}, "May", PERIOD)
    assert (rows[0].surname, rows[0].initials) == ("Botha", "P.J.")
    rows, _ = ui19.form_rows({"1": ytd(name="Lucy Baloyi")}, {}, "May", PERIOD)
    assert (rows[0].surname, rows[0].initials) == ("Baloyi", "L.")


def test_inclusion_rule():
    records = {
        "1": ytd("1"),                                                    # paid
        "2": ytd("2", earnings={}, uif={"May": 0.0}),                     # nothing
        "3": ytd("3", earnings={}, uif={"May": 0.0}, end="20250515"),     # unpaid leaver this month
        "4": ytd("4", earnings={}, uif={"May": 0.0}, start="20250520"),   # starts this month
        "5": ytd("5", earnings={}, uif={"May": 12.0}),                    # UIF only
        "6": ytd("6", earnings={}, uif={"May": 0.0}, end="20250415"),     # left earlier
    }
    rows, _ = ui19.form_rows(records, {}, "May", PERIOD)
    assert [r.employee_code for r in rows] == ["1", "3", "4", "5"]


def test_report_order_kept():
    rows, _ = ui19.form_rows({"10": ytd("10"), "2": ytd("2")}, {}, "May", PERIOD)
    assert [r.employee_code for r in rows] == ["10", "2"]


def test_dates_prefer_employee_record():
    rows, _ = ui19.form_rows(
        {"1": ytd(start="20190101", end="20250531")},
        {"1": emp(date_engaged="20200101", end_date="20250530")}, "May", PERIOD,
    )
    assert (rows[0].commencement_date, rows[0].termination_date) == ("20200101", "20250530")
    rows, _ = ui19.form_rows({"1": ytd(start="20190101", end="20250531")}, {}, "May", PERIOD)
    assert (rows[0].commencement_date, rows[0].termination_date) == ("20190101", "20250531")


def test_id_hours_gross():
    rows, _ = ui19.form_rows({"1": ytd()}, {"1": emp()}, "May", PERIOD)
    assert rows[0].id_number == "8306056177085"
    assert rows[0].hours_worked == 173.33
    assert rows[0].gross == 5000.0
    passport = emp(id_number="", passport_number="BN487879")
    rows, _ = ui19.form_rows({"1": ytd()}, {"1": passport}, "May", PERIOD)
    assert rows[0].id_number == "BN487879"


def test_contributor_rule():
    def contributor(employee, uif):
        employees = {"1": employee} if employee else {}
        rows, _ = ui19.form_rows({"1": ytd(uif=uif)}, employees, "May", PERIOD)
        return rows[0].uif_contributor

    assert contributor(emp(uif_status="Contributes"), {"May": 0.0}) == "YES"
    assert contributor(emp(uif_status="Does not contribute"), {"May": 50.0}) == "NO"
    assert contributor(emp(uif_status="Exempt"), {"May": 50.0}) == "NO"
    assert contributor(emp(uif_status=""), {"May": 50.0}) == "YES"
    assert contributor(None, {"May": 0.0}) == "NO"
    assert contributor(None, {}) == ""
    # Standard Format: the assumed "Contributes" is ignored, the deduction decides.
    assert contributor(emp(uif_status_reported=False), {"May": 0.0}) == "NO"


def test_warnings():
    records = {"1": ytd("1", uif={}), "2": ytd("2")}
    employees = {"2": emp("2", id_number="", passport_number="AB12345678901234")}
    _, warnings = ui19.form_rows(records, employees, "May", PERIOD)
    assert any("missing an ID/passport number" in w for w in warnings)
    assert any("1 employee(s) on the payroll this month were not found" in w for w in warnings)
    assert any("contributor Yes/No" in w for w in warnings)
    assert any("longer than the form's 13 boxes" in w for w in warnings)
    assert not any("hours worked" in w for w in warnings)   # employee data present


def test_codes():
    leaver = ui19.FormRow("3", "A", "B.", "", 0.0, None, "20200101", "20250515", "NO")
    future = ui19.FormRow("4", "C", "D.", "", 100.0, None, "20200101", "20250710", "NO")
    assert ui19.needs_termination_reason(leaver, PERIOD)
    assert not ui19.needs_termination_reason(future, PERIOD)
    assert ui19.default_non_contributor_reason(leaver) == "6"
    assert ui19.default_non_contributor_reason(future) is None
    ui19.apply_codes([leaver, future], PERIOD, {"3": "06", "4": "11"}, {"3": "6", "4": "1"})
    assert (leaver.termination_reason_code, leaver.non_contributor_reason_code) == ("6", "6")
    assert (future.termination_reason_code, future.non_contributor_reason_code) == ("", "1")
    assert list(ui19.NON_CONTRIBUTOR_REASONS) == [str(n) for n in range(1, 10)]
