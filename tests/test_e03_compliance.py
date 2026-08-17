"""
Conformance tests against ELECTRONIC DECLARATION SPECIFICATIONS - E03 (1).pdf.

Each test cites the rule it enforces. These cover the gaps found in the
2026-08-14 audit (docs/E03-COMPLIANCE.md); the pre-existing record structure
is covered by test_generate_003.py.
"""

import pytest

from uif import uif_ref, validate
from uif.generate_003 import _field, _q, build, terminations_for_months, to_ascii
from uif.models import Company, EmployeeRecord, MatchedRecord, YtdRecord


def _company(**overrides) -> Company:
    base = dict(
        uif_ref="020440843",
        paye_ref="7930795960",
        contact_name="Richard Coetzee",
        contact_phone="0122590848",
        contact_email_header="tax@elimperio.co.za",
        contact_email_footer="tax@elimperio.co.za",
        submission_mode="LIVE",
    )
    base.update(overrides)
    return Company(**base)


# The default DOB matches the first six digits of the fixture ID 8306056177085
# (830605), so sa_id.problems() stays clean unless a test opts into a bad ID.
def _matched(code, emp_kwargs, status="Employed", earnings=None, end_date=""):
    employee = None
    if emp_kwargs is not None:
        employee = EmployeeRecord(
            employee_code=code,
            surname=emp_kwargs.get("surname", "Surname"),
            first_names=emp_kwargs.get("first_names", "First"),
            id_number=emp_kwargs.get("id_number", ""),
            passport_number=emp_kwargs.get("passport_number", ""),
            date_of_birth=emp_kwargs.get("date_of_birth", "19830605"),
            date_engaged=emp_kwargs.get("date_engaged", "20140101"),
            end_date=emp_kwargs.get("end_date", ""),
            employee_status=emp_kwargs.get("employee_status", "Normal"),
            uif_status=emp_kwargs.get("uif_status", "Contributes"),
        )
    ytd = YtdRecord(
        employee_code=code,
        employee_name="Test Employee",
        status=status,
        end_date=end_date,
        earnings={"February": earnings if earnings is not None else {"Basic salary": 10000.0}},
    )
    return MatchedRecord(code, employee, ytd)


def _lines(records, company=None, overrides=None, period="202502"):
    raw = build(records, "February", period, company or _company(), overrides)
    return raw.decode("ascii").rstrip("\r\n").split("\r\n")


# --- 8020: reference normalisation (§8, rule 8020) ------------------------


def test_normalise_matches_spec_example():
    """§8: 'e.g. 123456/8 should be sent as 001234568'."""
    assert uif_ref.normalise("123456/8") == "001234568"


def test_normalise_zero_fills_and_strips_noise():
    assert uif_ref.normalise("20440843") == "020440843"
    assert uif_ref.normalise(" 2044084 / 3 ") == "020440843"


def test_normalise_does_not_truncate_an_over_long_reference():
    """Silently dropping a digit is worse than a visibly wrong reference."""
    assert uif_ref.normalise("1234567890") == "1234567890"


def test_header_and_employee_records_carry_the_normalised_reference():
    lines = _lines(
        [_matched("1", {"id_number": "8306056177085"})],
        company=_company(uif_ref="2044084/3"),
    )
    assert '8020,"020440843"' in lines[0]
    assert '8110,"020440843"' in lines[1]
    assert '8115,"020440843"' in lines[2]


# --- Appendix A: check digit ----------------------------------------------


def test_check_digit_reproduces_the_spec_worked_example():
    """Appendix A: reference 2648757, base 264875, total 27, check digit 7."""
    assert uif_ref.check_digit("264875") == 7


def test_check_digit_undefined_outside_a_six_digit_base():
    assert uif_ref.check_digit("2044084") is None
    assert uif_ref.check_digit("26487") is None


def test_check_digit_ok_validates_the_spec_example():
    assert uif_ref.check_digit_ok("002648757") is True
    assert uif_ref.check_digit_ok("002648751") is False


def test_check_digit_ok_declines_to_judge_a_longer_reference():
    """The real client reference 020440843 is 7 digits plus a check digit;
    Appendix A only supplies multipliers for 6. Reporting it invalid would
    block a perfectly good submission."""
    assert uif_ref.check_digit_ok("020440843") is None


def test_describe_warns_but_never_blocks_on_a_bad_check_digit():
    warnings = uif_ref.describe("002648751")
    assert len(warnings) == 1
    assert "check-digit" in warnings[0]


def test_describe_is_silent_on_a_good_reference():
    assert uif_ref.describe("020440843") == []
    assert uif_ref.describe("2648757") == []


# --- 8220: alternate number fallback (§8, rule 8220) ----------------------


def test_missing_id_and_passport_falls_back_to_8220():
    """§8: 8220 'should contain either the personnel, clock card or payroll
    number', and a record is rejected only when 8200, 8210 and 8220 are all
    absent."""
    lines = _lines([_matched("0042", {"surname": "Sithole"})])
    assert '8220,"0042"' in lines[1]
    assert "8200," not in lines[1]
    assert "8210," not in lines[1]


def test_id_number_still_preferred_over_the_fallback():
    lines = _lines([_matched("7", {"id_number": "8306056177085"})])
    assert "8200,8306056177085" in lines[1]
    assert "8220," not in lines[1]


def test_passport_preferred_over_the_fallback():
    lines = _lines([_matched("7", {"passport_number": "BN487879"})])
    assert '8210,"BN487879"' in lines[1]
    assert "8220," not in lines[1]


def test_missing_identity_number_is_a_warning_not_a_block():
    records = [_matched("0042", {"surname": "Sithole"})]
    blocking, soft = validate.validate(records, "February")
    assert blocking == []
    assert any("8220" in message for message in soft)


# --- 8290: reason for non-contribution (§8, rule 8290) --------------------


def test_zero_contribution_carries_a_reason_code():
    """§8: 'The Reason code for non-contribution is a required field if the
    UIF contribution amount is zero.'"""
    records = [
        _matched("1", {"id_number": "8306056177085"}, earnings={"Severance Pay": 50000.0})
    ]
    lines = _lines(records)
    # §4/§5: a zero field is omitted with its code. 8310 (remuneration) and 8320
    # (contribution) are both zero here and drop out; 8300 (the severance gross)
    # stays, and 8290 carries the reason.
    assert "8290,06" in lines[1]
    assert "8300," in lines[1]
    assert "8310," not in lines[1]
    assert "8320," not in lines[1]


def test_normal_contribution_omits_the_reason_code():
    lines = _lines([_matched("1", {"id_number": "8306056177085"})])
    assert "8290," not in lines[1]


# --- 8280: employment status (§8, rule 8280) ------------------------------


def _terminated(code="1", end_date="20250115"):
    return _matched(
        code,
        {"id_number": "8306056177085"},
        status="Terminated",
        end_date=end_date,
    )


def test_termination_defaults_to_the_payroll_derived_code():
    lines = _lines([_terminated()])
    assert "8270,20250115" in lines[1]
    assert "8280,06" in lines[1]


def test_status_override_replaces_the_default_code():
    lines = _lines([_terminated()], overrides={"1": "11"})
    assert "8280,11" in lines[1]
    assert "8280,06" not in lines[1]
    assert "8270,20250115" in lines[1]


def test_override_to_a_still_employed_code_drops_the_end_date():
    """§9 warns when 'the date employed to is valid, and field 8280 is 01, 09
    or 10' — those codes describe someone who has not left."""
    for code in ("01", "09", "10"):
        lines = _lines([_terminated()], overrides={"1": code})
        assert f"8280,{code}" in lines[1]
        assert "8270," not in lines[1]


def test_override_does_not_leak_to_an_untermined_employee():
    records = [_matched("1", {"id_number": "8306056177085"})]
    lines = _lines(records, overrides={"1": "11"})
    assert "8280,01" in lines[1]
    assert "8280,11" not in lines[1]


def test_terminations_listed_once_across_months():
    record = _matched(
        "1", {"id_number": "8306056177085"}, status="Terminated", end_date="20250115"
    )
    record.ytd.earnings["January"] = {"Basic salary": 5000.0}
    found = terminations_for_months(
        [record], ["January", "February"], {"January": "202501", "February": "202502"}
    )
    assert [r.employee_code for r in found] == ["1"]


def test_termination_after_the_declared_period_is_not_yet_reported():
    lines = _lines([_terminated(end_date="20250320")], period="202502")
    assert "8270," not in lines[1]
    assert "8280,01" in lines[1]


# --- 8240 / field lengths (§7 record layouts) -----------------------------


def test_first_names_are_not_truncated_to_twelve():
    """§7: 8240 is Alphanumeric 90. The old 12-char cut lost real data."""
    lines = _lines([_matched("1", {
        "id_number": "8306056177085", "first_names": "Johannes Christiaan Petrus"
    })])
    assert '8240,"Johannes Christiaan Petrus"' in lines[1]


def test_first_names_capped_at_the_declared_ninety():
    lines = _lines([_matched("1", {
        "id_number": "8306056177085", "first_names": "A" * 200
    })])
    assert f'8240,"{"A" * 90}"' in lines[1]


def test_surname_capped_at_the_declared_one_hundred_and_twenty():
    lines = _lines([_matched("1", {
        "id_number": "8306056177085", "surname": "B" * 200
    })])
    assert f'8230,"{"B" * 120}"' in lines[1]


# --- ASCII output (§5) ----------------------------------------------------


def test_to_ascii_transliterates_rather_than_replacing():
    assert to_ascii("Böhme") == "Bohme"
    assert to_ascii("Grüné") == "Grune"
    assert to_ascii("Sørensen") == "Sorensen"
    assert to_ascii("O'Reilly") == "O'Reilly"


def test_output_is_pure_ascii():
    """§5: 'The file must be submitted in ASCII format.'"""
    raw = build(
        [_matched("1", {"id_number": "8306056177085", "surname": "Böhme"})],
        "February",
        "202502",
        _company(),
    )
    raw.decode("ascii")  # raises if any byte is >127
    assert b'8230,"Bohme"' in raw


# --- 8120 PAYE reference (§8, rule 8120) ----------------------------------


def test_paye_reference_shape_is_warned_about():
    """§8: 'This number starts with a "7" and must be a valid reference
    number as supplied by SARS.'"""
    assert validate.validate_company(_company()) == []
    assert any(
        "PAYE" in w for w in validate.validate_company(_company(paye_ref="1234567890"))
    )
    assert any(
        "PAYE" in w for w in validate.validate_company(_company(paye_ref="79307"))
    )


@pytest.mark.parametrize("ref", ["020440843", "2044084/3", "20440843"])
def test_company_validation_accepts_the_real_reference_in_any_form(ref):
    assert validate.validate_company(_company(uif_ref=ref)) == []


# --- 8200 / 8220 when the ID is invalid (rule 8200 + rule 8220) ------------


def test_invalid_id_emits_both_8200_and_8220():
    """§8 rule 8220: 'mandatory if fields 8200 or 8210 are invalid or not
    present'. A present-but-invalid ID keeps 8200 and adds 8220 (the payroll
    number) so the Fund can track the contribution while the ID is held in the
    secondary database."""
    lines = _lines([_matched("0042", {"id_number": "8306060000000"})])  # Excel-mangled
    body = lines[1]
    assert "8200,8306060000000" in body
    assert '8220,"0042"' in body
    assert body.index("8200,") < body.index("8220,") < body.index("8230,")


def test_valid_id_has_no_8220():
    lines = _lines([_matched("7", {"id_number": "8306056177085"})])
    assert "8200,8306056177085" in lines[1]
    assert "8220," not in lines[1]


def test_invalid_id_is_a_soft_warning_with_the_consequence_spelled_out():
    records = [_matched("0042", {"id_number": "8306060000000"})]
    blocking, soft = validate.validate(records, "February")
    assert blocking == []
    warning = next(w for w in soft if "8306060000000" in w)
    assert "scientific-notation" in warning
    assert "cannot claim" in warning
    assert "Number, 0 decimals" in warning       # the Excel fix hint


# --- §5 quote / control-char folding --------------------------------------


def test_curly_double_quotes_fold_to_apostrophe_not_a_straight_quote():
    """§5 wraps alphanumeric fields in double quotes and defines no escaping, so
    a curly double quote must fold to an apostrophe, never a straight quote that
    would break the field."""
    assert to_ascii("O“Reilly”") == "O'Reilly'"
    assert _q("O“Reilly”") == "\"O'Reilly'\""


def test_straight_double_quote_in_a_field_becomes_an_apostrophe():
    assert _field("8230", 'Sm"ith') == "\"Sm'ith\""


def test_control_chars_in_a_field_collapse_to_a_single_space():
    assert _q("Sm\nith") == '"Sm ith"'
    assert _q("a\r\n\tb") == '"a   b"'


def test_comma_in_a_name_warns_but_is_written_unchanged():
    records = [_matched("1", {"id_number": "8306056177085", "surname": "Smith, Jr"})]
    _, soft = validate.validate(records, "February")
    assert any("comma" in w for w in soft)
    lines = _lines(records)
    assert '8230,"Smith, Jr"' in lines[1]         # value not mutated


# --- §4/§5 zero-field omission --------------------------------------------


def test_footer_omits_zero_totals_but_keeps_the_record_count():
    """An all-zero (empty) month still writes 8150; the zero currency totals
    8130/8135/8140 are omitted per §4/§5."""
    footer = _lines([])[-1]
    assert "8130," not in footer
    assert "8135," not in footer
    assert "8140," not in footer
    assert "8150,0" in footer
