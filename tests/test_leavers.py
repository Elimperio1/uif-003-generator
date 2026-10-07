"""Possible leavers: employees the payroll data suggests have left without saying so."""

from uif import generate_003
from uif.leavers import confirm_leaver, possible_leavers
from uif.models import EmployeeRecord, MatchedRecord, YtdRecord, period_code

PERIODS = {m: period_code(m, 2027) for m in ("May", "June", "July", "August")}


def _rec(code, earnings, status="Employed", end_date="", emp_end=""):
    emp = EmployeeRecord(
        employee_code=code, surname="Smit", first_names="Jan", id_number="",
        passport_number="", date_of_birth="19830605", date_engaged="20200101",
        end_date=emp_end, employee_status="Normal", uif_status="Contributes",
    )
    ytd = YtdRecord(
        employee_code=code, employee_name="Jan Smit", status=status,
        end_date=end_date,
        earnings={m: {"Basic salary": amt} for m, amt in earnings.items()},
    )
    return MatchedRecord(code, emp, ytd)


# A second, always-paid employee so every month counts as "has data".
STEADY = _rec("99", {"May": 1, "June": 1, "July": 1, "August": 1})


def test_stopped_being_paid_is_flagged_with_last_paid_month():
    rec = _rec("1", {"May": 5000, "June": 5000})
    found = possible_leavers([rec, STEADY], ["July"], PERIODS, already=set())
    assert [p.record.employee_code for p in found] == ["1"]
    assert found[0].last_paid == "June"
    assert found[0].end_date == ""
    assert "July" in found[0].why


def test_unpaid_months_are_listed_once_per_employee():
    rec = _rec("1", {"May": 5000})
    found = possible_leavers([rec, STEADY], ["June", "July"], PERIODS, already=set())
    assert len(found) == 1
    assert "June" in found[0].why and "July" in found[0].why


def test_never_paid_before_is_not_flagged():
    rec = _rec("1", {"August": 5000})
    assert possible_leavers([rec, STEADY], ["July"], PERIODS, already=set()) == []


def test_month_with_no_payroll_data_flags_nobody():
    rec = _rec("1", {"May": 5000})
    steady = _rec("99", {"May": 1})
    assert possible_leavers([rec, steady], ["July"], PERIODS, already=set()) == []


def test_end_date_with_employed_status_is_flagged():
    rec = _rec("1", {"June": 5000}, end_date="20260620")
    found = possible_leavers([rec, STEADY], ["June"], PERIODS, already=set())
    assert len(found) == 1
    assert found[0].end_date == "20260620"
    assert "Employed" in found[0].why


def test_end_date_from_employee_details_counts():
    rec = _rec("1", {"June": 5000}, emp_end="20260620")
    found = possible_leavers([rec, STEADY], ["June"], PERIODS, already=set())
    assert found[0].end_date == "20260620"


def test_end_date_after_the_period_is_not_flagged():
    rec = _rec("1", {"June": 5000}, end_date="20260920")
    assert possible_leavers([rec, STEADY], ["June"], PERIODS, already=set()) == []


def test_payroll_marked_leaver_is_not_flagged():
    rec = _rec("1", {"June": 5000}, status="No longer employed", end_date="20260620")
    assert possible_leavers([rec, STEADY], ["June", "July"], PERIODS, already=set()) == []


def test_already_listed_leavers_are_skipped():
    rec = _rec("1", {"May": 5000})
    assert possible_leavers([rec, STEADY], ["July"], PERIODS, already={"1"}) == []


def test_confirmed_leaver_is_declared_terminated_in_edecs():
    rec = _rec("1", {"June": 5000})
    confirmed = confirm_leaver(rec, "20260630")
    assert generate_003.is_terminated_in_period(confirmed, PERIODS["June"])
    assert generate_003.termination_date(confirmed) == "20260630"
    # The original record is untouched (parses are cached).
    assert rec.ytd.status == "Employed" and rec.ytd.end_date == ""


def test_confirm_keeps_the_payroll_end_date():
    rec = _rec("1", {"June": 5000}, end_date="20260620")
    assert confirm_leaver(rec, "").ytd.end_date == "20260620"
