"""
SA ID validation — E03 spec rule 8200 + Appendix B. Every check is warning-only
(spec §8/§9/§10: an invalid ID is held in a secondary database, never rejected).
"""

from uif import sa_id
from uif.parse_employees import parse_id_number


# --- Appendix B check digit ------------------------------------------------


def test_check_digit_reproduces_the_spec_worked_example():
    """Appendix B works the example 6407150083005 → valid."""
    assert sa_id.check_digit_ok("6407150083005") is True


def test_check_digit_rejects_a_flipped_last_digit():
    assert sa_id.check_digit_ok("6407150083004") is False


def test_check_digit_none_when_not_exactly_thirteen_digits():
    assert sa_id.check_digit_ok("64071500830") is None       # 11
    assert sa_id.check_digit_ok("64071500830055") is None     # 14
    assert sa_id.check_digit_ok("64071500830X5") is None      # non-digit


# --- Excel corruption signature --------------------------------------------


def test_excel_signature_passes_check_digit_yet_is_flagged():
    """8306060000000 is exactly why the check digit alone is not enough: it
    *passes* Appendix B by coincidence but is a scientific-notation corpse
    (ends in four or more zeros)."""
    assert sa_id.check_digit_ok("8306060000000") is True
    assert sa_id.excel_corruption_signature("8306060000000") is True
    problems = sa_id.problems("8306060000000", "19830606")
    assert len(problems) == 1
    assert "scientific-notation" in problems[0]


def test_signature_threshold_stays_at_four_zeros():
    # Real SA IDs can legitimately end in up to three zeros — never flag those.
    assert sa_id.excel_corruption_signature("1234567891000") is False   # 3 zeros
    assert sa_id.excel_corruption_signature("1234567890000") is True    # 4 zeros


# --- problems() ------------------------------------------------------------


def test_problems_empty_for_a_missing_id():
    assert sa_id.problems("", "19830605") == []


def test_problems_not_thirteen_digits():
    problems = sa_id.problems("6407150083", "")      # 10 digits
    assert len(problems) == 1
    assert "13 digits" in problems[0]


def test_problems_check_digit_failure():
    problems = sa_id.problems("6407150083004", "")
    assert len(problems) == 1
    assert "check-digit" in problems[0]


def test_problems_dob_mismatch_only_fires_when_structurally_ok():
    problems = sa_id.problems("6407150083005", "19990101")   # ID says 640715
    assert len(problems) == 1
    assert "date of birth" in problems[0]
    # a matching DOB is clean
    assert sa_id.problems("6407150083005", "19640715") == []


def test_twelve_digit_id_is_padded_by_parser_then_validates():
    """A leading-zero ID that Excel stripped to 12 digits is padded to 13 by the
    parser, then passes Appendix B."""
    padded = parse_id_number("101166305082")     # 12 digits in
    assert padded == "0101166305082"
    assert sa_id.check_digit_ok(padded) is True
    assert sa_id.problems(padded, "19010116") == []
