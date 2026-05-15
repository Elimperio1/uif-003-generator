"""Unit tests for uif.generate_003."""

from decimal import Decimal

from uif.generate_003 import _fmt, build, employee_figures, included_for_month
from uif.models import Company, EmployeeRecord, MatchedRecord, YtdRecord


def _company() -> Company:
    return Company(
        uif_ref="020440843",
        paye_ref="7930795960",
        contact_name="Richard Coetzee",
        contact_phone="0122590848",
        contact_email_header="tax@elimperio.co.za",
        contact_email_footer="tax@elimperio.co.za",
        submission_mode="LIVE",
        file_extension="003",
    )


def _matched(code, emp_kwargs, status, earnings, end_date=""):
    employee = EmployeeRecord(
        employee_code=code,
        surname=emp_kwargs["surname"],
        first_names=emp_kwargs["first_names"],
        id_number=emp_kwargs.get("id_number", ""),
        passport_number=emp_kwargs.get("passport_number", ""),
        date_of_birth=emp_kwargs["date_of_birth"],
        date_engaged=emp_kwargs["date_engaged"],
        end_date=emp_kwargs.get("end_date", ""),
        employee_status=emp_kwargs.get("employee_status", "Normal"),
        uif_status="Contributes",
    )
    ytd = YtdRecord(
        employee_code=code,
        employee_name=f"{emp_kwargs['first_names']} {emp_kwargs['surname']}",
        status=status,
        end_date=end_date,
        earnings={"February": earnings},
    )
    return MatchedRecord(code, employee, ytd)


def test_fmt_strips_trailing_double_zero():
    assert _fmt(11550.0) == "11550"
    assert _fmt(17712.0) == "17712"
    assert _fmt(0.0) == "0"


def test_fmt_keeps_real_decimals():
    assert _fmt(6232.80) == "6232.80"
    assert _fmt(354.24) == "354.24"
    assert _fmt(198.68) == "198.68"


def test_employee_figures_uncapped():
    record = _matched(
        "1",
        {"surname": "Bonde", "first_names": "Abel", "passport_number": "BN487879",
         "date_of_birth": "19840618", "date_engaged": "20140101"},
        "Employed",
        {"Basic salary": 9933.52},
    )
    gross, remuneration, uif_total = employee_figures(record, "February")
    assert gross == 9933.52
    assert remuneration == 9933.52
    # round(99.3352, 2) = 99.34 ; 99.34 * 2 = 198.68 (NOT 198.67)
    assert uif_total == Decimal("198.68")


def test_employee_figures_capped_at_17712():
    record = _matched(
        "2",
        {"surname": "Sprong", "first_names": "Johann", "id_number": "8409015005080",
         "date_of_birth": "19840901", "date_engaged": "20220301"},
        "Employed",
        {"Basic salary": 39220.00},
    )
    gross, remuneration, uif_total = employee_figures(record, "February")
    assert gross == 39220.00
    assert remuneration == 17712.00
    assert uif_total == Decimal("354.24")


def test_included_for_month_excludes_zero_earners():
    earner = _matched(
        "1",
        {"surname": "A", "first_names": "A", "id_number": "1" * 13,
         "date_of_birth": "19800101", "date_engaged": "20200101"},
        "Employed",
        {"Basic salary": 100.0},
    )
    zero = _matched(
        "2",
        {"surname": "B", "first_names": "B", "id_number": "2" * 13,
         "date_of_birth": "19800101", "date_engaged": "20200101"},
        "Employed",
        {"Basic salary": 0.0},
    )
    included = included_for_month([zero, earner], "February")
    assert [r.employee_code for r in included] == ["1"]


def test_build_produces_expected_bytes():
    bonde = _matched(
        "1",
        {"surname": "Bonde", "first_names": "Abel", "passport_number": "BN487879",
         "date_of_birth": "19840618", "date_engaged": "20140101"},
        "Employed",
        {"Basic salary": 9933.52},
    )
    sprong = _matched(
        "2",
        {"surname": "Sprong", "first_names": "Johann", "id_number": "8409015005080",
         "date_of_birth": "19840901", "date_engaged": "20220301"},
        "Employed",
        {"Basic salary": 39220.00},
    )
    output = build([sprong, bonde], "February", "202402", _company())

    expected = (
        '8000,"UICR",8010,"U1",8015,"E03",8020,"020440843",8030,"LIVE",'
        '8040,"Richard Coetzee",8050,"0122590848",'
        '8060,"tax@elimperio.co.za",8070,202402\r\n'
        '8001,"UIWK",8110,"020440843",8210,"BN487879",8230,"Bonde",8240,"Abel",'
        "8250,19840618,8260,20140101,8280,01,"
        "8300,9933.52,8310,9933.52,8320,198.68\r\n"
        '8001,"UIWK",8110,"020440843",8200,8409015005080,8230,"Sprong",'
        '8240,"Johann",8250,19840901,8260,20220301,8280,01,'
        "8300,39220,8310,17712,8320,354.24\r\n"
        '8002,"UIEM",8115,"020440843",8120,7930795960,'
        "8130,49153.52,8135,27645.52,8140,552.92,8150,2,"
        '8160,"tax@elimperio.co.za"\r\n'
    )
    assert output.decode("latin-1") == expected


def test_build_terminated_employee_carries_end_date_and_status_06():
    terminated = _matched(
        "1",
        {"surname": "Kwepile", "first_names": "Lawrance", "id_number": "5811105978089",
         "date_of_birth": "19581110", "date_engaged": "20170801"},
        "No longer employed",
        {"Basic salary": 5407.20},
        end_date="20231231",
    )
    output = build([terminated], "February", "202402", _company()).decode("latin-1")
    assert "8270,20231231,8280,06," in output
