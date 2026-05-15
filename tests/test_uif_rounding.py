from decimal import Decimal
from uif.generate_003 import compute_uif_total


def test_qotoyi_exact_half_cent():
    """6492.50 → 129.85 exact → must round UP to 129.86 (the actual bug)."""
    assert compute_uif_total(Decimal("6492.50")) == Decimal("129.86")


def test_clean_amount_no_rounding():
    """11550.00 × 0.02 = 231.00 exact."""
    assert compute_uif_total(Decimal("11550.00")) == Decimal("231.00")


def test_capped_amount():
    """17712.00 × 0.02 = 354.24 exact."""
    assert compute_uif_total(Decimal("17712.00")) == Decimal("354.24")


def test_5478_67():
    """5478.67 × 0.01 = 54.7867 → 54.79 per half → 109.58 total."""
    assert compute_uif_total(Decimal("5478.67")) == Decimal("109.58")


def test_accepts_float():
    assert compute_uif_total(6492.50) == Decimal("129.86")


def test_accepts_string():
    assert compute_uif_total("6492.50") == Decimal("129.86")


def test_zero():
    assert compute_uif_total(Decimal("0")) == Decimal("0.00")
