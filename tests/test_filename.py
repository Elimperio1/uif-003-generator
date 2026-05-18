from uif.generate_003 import build_filename


def test_strips_single_leading_zero():
    assert build_filename("020440843", 1) == "20440843.001"


def test_strips_multiple_leading_zeros():
    assert build_filename("000123456", 5) == "123456.005"


def test_no_leading_zero_unchanged():
    assert build_filename("120440843", 1) == "120440843.001"


def test_sequence_zero_padded_to_three_digits():
    assert build_filename("020440843", 1) == "20440843.001"
    assert build_filename("020440843", 9) == "20440843.009"
    assert build_filename("020440843", 10) == "20440843.010"
    assert build_filename("020440843", 12) == "20440843.012"


def test_sequence_above_twelve_still_zero_padded():
    """Defensive: we only expect 1-12 in practice but the format shouldn't break."""
    assert build_filename("020440843", 99) == "20440843.099"
    assert build_filename("020440843", 100) == "20440843.100"


def test_full_year_batch_sequence():
    """A full SA tax year produces .001 through .012 in march-first order."""
    filenames = [build_filename("020440843", i) for i in range(1, 13)]
    assert filenames[0] == "20440843.001"   # March
    assert filenames[-1] == "20440843.012"  # February
    assert len(set(filenames)) == 12         # all unique


def test_all_zero_ref_falls_back_to_zero():
    """Edge case: defensive against an all-zero ref, which shouldn't ever
    happen but shouldn't produce an empty basename either."""
    assert build_filename("000000000", 1) == "0.001"
