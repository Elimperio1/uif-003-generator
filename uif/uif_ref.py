"""
UIF employer reference number (field 8020 / 8110 / 8115) handling.

Spec: ``ELECTRONIC DECLARATION SPECIFICATIONS - E03 (1).pdf`` §8 (rule 8020),
§12 (file naming) and Appendix A (check digit).

An invalid 8020 rejects the *entire* file, so normalisation happens before the
value ever reaches a record.
"""

from __future__ import annotations

# Spec §8, rule 8020: "must be zero filled from the left" to the field's
# declared Alphanumeric-9 length.
REF_LENGTH = 9

# Appendix A multipliers, applied left to right across the base digits.
# The worked example (2648757 -> base 264875, check digit 7) is the only
# case the spec defines, and it is six base digits long.
_CHECK_DIGIT_MULTIPLIERS = (2, 4, 5, 7, 8, 2)
_CHECKABLE_BASE_LENGTH = len(_CHECK_DIGIT_MULTIPLIERS)


def normalise(raw: str) -> str:
    """
    Normalise a UIF reference to the form field 8020 requires.

    Spec §8: "must be a valid UIF reference number, must be zero filled from
    the left, and must exclude any non-numeric characters e.g. 123456/8 should
    be sent as 001234568."

    Args:
        raw: Whatever the user typed, e.g. ``"123456/8"``, ``" 20440843 "``.

    Returns:
        Digits only, zero-filled from the left to 9 characters. A reference
        already longer than 9 digits is returned unpadded rather than
        truncated — silently dropping a digit would be worse than emitting a
        value the Fund can reject visibly.

    Examples:
        >>> normalise("123456/8")
        '001234568'
        >>> normalise("20440843")
        '020440843'
        >>> normalise("2044084 3")
        '020440843'
    """
    digits = "".join(char for char in raw if char.isdigit())
    return digits.zfill(REF_LENGTH)


def check_digit(base: str) -> int | None:
    """
    Compute the Appendix A check digit for a reference's base digits.

    The routine multiplies each base digit by its positional multiplier, takes
    each product modulo 11, and sums those remainders. A total below 10 is
    itself the check digit; otherwise the total's second digit is used.

    Args:
        base: The reference digits *excluding* the trailing check digit.

    Returns:
        The expected check digit, or ``None`` when ``base`` is not the six
        digits Appendix A defines the multipliers for.
    """
    if len(base) != _CHECKABLE_BASE_LENGTH or not base.isdigit():
        return None
    total = sum(
        (int(digit) * multiplier) % 11
        for digit, multiplier in zip(base, _CHECK_DIGIT_MULTIPLIERS)
    )
    # A total of 27 gives check digit 7; a total below 10 is used as-is. The
    # maximum possible total is 60, so "second digit" is always the units.
    return total if total < 10 else total % 10


def check_digit_ok(ref: str) -> bool | None:
    """
    Verify a normalised reference against the Appendix A check digit.

    Returns ``None`` — meaning "cannot be checked" — for any reference whose
    base is not six digits long. Appendix A only supplies multipliers for a
    six-digit base (its example, 123456/8, is six digits plus a check digit),
    and real seven-digit references such as 2044084/3 do not validate under
    any straightforward extension of the published routine. Reporting those as
    invalid would reject perfectly good reference numbers, so they are left
    unchecked.
    """
    digits = "".join(char for char in ref if char.isdigit()).lstrip("0")
    if len(digits) != _CHECKABLE_BASE_LENGTH + 1:
        return None
    expected = check_digit(digits[:-1])
    if expected is None:
        return None
    return expected == int(digits[-1])


def describe(raw: str) -> list[str]:
    """
    Soft warnings about a reference the user typed. Never blocking.

    The normalised value is always usable; these messages flag the cases where
    it is probably not the number the filer meant.
    """
    warnings: list[str] = []
    digits = "".join(char for char in raw if char.isdigit())

    if not digits:
        return ["UIF reference number contains no digits."]
    if len(digits) > REF_LENGTH:
        warnings.append(
            f"UIF reference number has {len(digits)} digits; field 8020 allows "
            f"{REF_LENGTH}. It is being sent unchanged — check it before "
            f"submitting, because an invalid 8020 rejects the whole file."
        )
    if check_digit_ok(normalise(raw)) is False:
        warnings.append(
            f"UIF reference number {normalise(raw)} fails the check-digit test "
            f"in Appendix A of the E03 spec. An invalid 8020 rejects the whole "
            f"file — verify the number before submitting."
        )
    return warnings
