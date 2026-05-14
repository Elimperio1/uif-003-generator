"""Unit tests for uif.models."""

from uif.models import YtdRecord, period_code


def test_period_code_february_is_end_year():
    assert period_code("February", 2025) == "202502"
    assert period_code("January", 2025) == "202501"


def test_period_code_march_to_december_is_prior_year():
    assert period_code("March", 2025) == "202403"
    assert period_code("December", 2025) == "202412"


def test_ytd_gross_sums_line_items():
    record = YtdRecord(
        employee_code="1",
        employee_name="Test",
        status="Employed",
        earnings={"February": {"Basic salary": 6488.16, "Overtime 1.5": 405.51}},
    )
    assert record.gross("February") == 6893.67


def test_ytd_remunerable_applies_remunerability_map():
    record = YtdRecord(
        employee_code="1",
        employee_name="Test",
        status="Employed",
        earnings={
            "February": {
                "Basic salary": 6488.16,
                "Travel allowance - 80%": 500.0,  # 80% remunerable -> 400.0
                "Overtime 1.5": 405.51,
            }
        },
    )
    # 6488.16 + 400.00 + 405.51
    assert record.remunerable("February") == 7293.67


def test_ytd_remunerable_excludes_severance_pay():
    record = YtdRecord(
        employee_code="1",
        employee_name="Test",
        status="Employed",
        earnings={"February": {"Basic salary": 5000.0, "Severance Pay": 20000.0}},
    )
    assert record.gross("February") == 25000.0
    assert record.remunerable("February") == 5000.0


def test_ytd_gross_zero_for_missing_month():
    record = YtdRecord(employee_code="1", employee_name="Test", status="Employed")
    assert record.gross("July") == 0.0
    assert record.remunerable("July") == 0.0
