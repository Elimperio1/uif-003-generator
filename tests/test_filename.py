"""
Filename rules, E03 spec §12.

"uuuuuuuu = UIF reference number ... The last 8 digits of the creator's UIF
Reference number (field 8020) must be used. Only numeric digits are allowed
and the slash between the last two digits must be excluded."
"""

from uif.generate_003 import build_filename


def test_spec_worked_example():
    """§12: 'the third submission by a creator with a UIF reference number of
    1234567/8 must have the following file name: 12345678.003'."""
    assert build_filename("1234567/8", 3) == "12345678.003"
    assert build_filename("012345678", 3) == "12345678.003"


def test_real_sample_reference():
    """The Sage samples this app was built against: 020440843 -> 20440843."""
    assert build_filename("020440843", 1) == "20440843.001"


def test_last_eight_digits_not_leading_zeros_stripped():
    """A short reference keeps its zero fill: the rule is 'last 8 digits',
    not 'strip leading zeros'. The two only agree for 0 + 8 digits."""
    assert build_filename("000123456", 5) == "00123456.005"


def test_over_length_reference_takes_last_eight():
    assert build_filename("123456789", 1) == "23456789.001"


def test_non_numeric_characters_excluded():
    assert build_filename("2044084/3", 1) == "20440843.001"
    assert build_filename(" 2044084 3 ", 1) == "20440843.001"


def test_sequence_zero_padded_to_three_digits():
    assert build_filename("020440843", 1) == "20440843.001"
    assert build_filename("020440843", 9) == "20440843.009"
    assert build_filename("020440843", 10) == "20440843.010"
    assert build_filename("020440843", 12) == "20440843.012"


def test_sequence_above_twelve_still_zero_padded():
    """§12 allows any 3-digit file number, not just a 12-month tax year."""
    assert build_filename("020440843", 99) == "20440843.099"
    assert build_filename("020440843", 100) == "20440843.100"


def test_full_year_batch_sequence():
    """A full SA tax year produces .001 through .012 in march-first order."""
    filenames = [build_filename("020440843", i) for i in range(1, 13)]
    assert filenames[0] == "20440843.001"   # March
    assert filenames[-1] == "20440843.012"  # February
    assert len(set(filenames)) == 12         # all unique


def test_batch_can_start_above_one():
    """Spec §12/§13: a repeat filename overwrites the earlier submission, so
    a second batch must start above the highest number already sent."""
    filenames = [build_filename("020440843", i) for i in range(13, 25)]
    assert filenames[0] == "20440843.013"
    assert filenames[-1] == "20440843.024"


def test_all_zero_ref_stays_zero_filled():
    """Edge case: an all-zero ref shouldn't ever happen, but the last-8 rule
    is still well defined for it."""
    assert build_filename("000000000", 1) == "00000000.001"
