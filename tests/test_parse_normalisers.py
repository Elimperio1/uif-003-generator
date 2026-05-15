from uif.parse_employees import (
    _normalise_numeric_string,
    parse_employee_code,
    parse_id_number,
)


# --- _normalise_numeric_string ---

def test_normalise_bare_int():
    assert _normalise_numeric_string("32") == "32"


def test_normalise_decimal_suffix():
    assert _normalise_numeric_string("32.00") == "32"


def test_normalise_decimal_suffix_long_id():
    assert _normalise_numeric_string("8306056177085.00") == "8306056177085"


def test_normalise_scientific_notation():
    """Scientific notation expands to the corrupted-but-detectable form."""
    assert _normalise_numeric_string("8.30606E+12") == "8306060000000"


def test_normalise_blank_and_none():
    assert _normalise_numeric_string("") == ""
    assert _normalise_numeric_string(None) == ""
    assert _normalise_numeric_string("   ") == ""


def test_normalise_non_numeric_falls_back_to_digits():
    """Non-numeric strings get digit-only extraction (e.g. passport-like)."""
    assert _normalise_numeric_string("BN487879") == "487879"


# --- parse_employee_code ---

def test_employee_code_2024_format():
    assert parse_employee_code("32.00") == "32"


def test_employee_code_2026_format():
    assert parse_employee_code("32") == "32"


def test_employee_code_both_formats_match():
    """Critical: the join key must be identical regardless of format."""
    assert parse_employee_code("32.00") == parse_employee_code("32")
    assert parse_employee_code("14.00") == parse_employee_code("14")
    assert parse_employee_code("1.00") == parse_employee_code("1")


# --- parse_id_number ---

def test_id_clean_13_digits():
    assert parse_id_number("8306056177085") == "8306056177085"


def test_id_with_decimal_suffix():
    assert parse_id_number("8306056177085.00") == "8306056177085"


def test_id_with_lost_leading_zero():
    """SA IDs starting with 0 lose the zero during numeric coercion — pad it back."""
    assert parse_id_number("101166305082") == "0101166305082"
    assert parse_id_number("101166305082.00") == "0101166305082"


def test_id_scientific_notation_preserves_corruption_signature():
    """The corruption detector relies on trailing zeros — make sure they survive."""
    result = parse_id_number("8.30606E+12")
    assert result == "8306060000000"
    assert result.endswith("000000")  # detector will catch this
