from uif.validate import looks_like_missing_decimal


# --- legitimate values pass ---

def test_legitimate_decimal():
    assert looks_like_missing_decimal("5000.00") is False
    assert looks_like_missing_decimal("103.45") is False
    assert looks_like_missing_decimal("0.50") is False
    assert looks_like_missing_decimal("17712.00") is False


def test_zero_passes():
    assert looks_like_missing_decimal("0") is False
    assert looks_like_missing_decimal("0.00") is False


def test_blank_passes():
    assert looks_like_missing_decimal("") is False
    assert looks_like_missing_decimal(None) is False
    assert looks_like_missing_decimal("   ") is False


def test_negative_decimal_passes():
    assert looks_like_missing_decimal("-103.45") is False


def test_float_input_passes():
    """Float types always have str() representation with decimal."""
    assert looks_like_missing_decimal(103.45) is False
    assert looks_like_missing_decimal(5000.00) is False


# --- the actual bug: pure integers flagged ---

def test_pure_integer_flagged():
    """The real bug case — value "103,45" stripped to "10345"."""
    assert looks_like_missing_decimal("10345") is True


def test_typical_corrupted_values_flagged():
    """Examples of what the bug looks like in practice."""
    assert looks_like_missing_decimal("500000") is True      # was "5000,00"
    assert looks_like_missing_decimal("1234556") is True     # was "12345,56"
    assert looks_like_missing_decimal("9999") is True        # was "99,99"


def test_negative_integer_flagged():
    """Even rarer but should still be caught."""
    assert looks_like_missing_decimal("-10345") is True


def test_handles_whitespace():
    assert looks_like_missing_decimal("  10345  ") is True
    assert looks_like_missing_decimal("  103.45  ") is False


def test_single_digit_integer_flagged():
    """Sage always exports decimals, so even small integers are suspect."""
    assert looks_like_missing_decimal("5") is True
    assert looks_like_missing_decimal("99") is True
