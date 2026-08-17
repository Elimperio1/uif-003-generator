"""
SA ID number validation for field 8200 — E03 spec rule 8200 and Appendix B.

Every check in this module is *warning-only*. Spec §8/§9 and §10: an invalid or
absent ID number produces a warning, not a rejection — the record is accepted,
the employee's details are held in a secondary database, and the employee simply
cannot claim benefits until the ID is corrected. A false rejection would cost the
whole filing, so nothing here ever blocks; callers surface these as soft
warnings only.
"""

from __future__ import annotations


def check_digit_ok(id13: str) -> bool | None:
    """
    Verify the 13th digit of an SA ID against Appendix B of the E03 spec.

    Appendix B (worked in the spec with ID ``6407150083005``):
      a) sum the digits in the odd positions 1, 3, …, 11 (indexes 0, 2, …, 10);
      b) concatenate the digits in the even positions 2, 4, …, 12
         (indexes 1, 3, …, 11) into one number, multiply it by 2, and sum the
         digits of the product;
      c) add (a) and (b) to a total;
      d) the check digit is ``(10 − total mod 10) mod 10`` and must equal the
         13th digit.

    Returns ``None`` when ``id13`` is not exactly 13 digits — there is nothing to
    check. Reproduces the spec's worked example (``6407150083005`` is valid).
    """
    if len(id13) != 13 or not id13.isdigit():
        return None
    odd_sum = sum(int(id13[i]) for i in range(0, 11, 2))
    even_doubled = int("".join(id13[i] for i in range(1, 12, 2))) * 2
    even_sum = sum(int(digit) for digit in str(even_doubled))
    total = odd_sum + even_sum
    check = (10 - total % 10) % 10
    return check == int(id13[12])


def excel_corruption_signature(id13: str) -> bool:
    """
    True when a 13-digit ID ends in **four or more** zeros — the fingerprint of
    an SA ID that Excel coerced into scientific notation (``8.30606E+12``) and
    that :func:`uif.parse_employees.parse_id_number` then expanded back into
    ``8306060000000``.

    ``8306060000000`` even *passes* the Appendix B check digit by coincidence,
    which is precisely why the check digit alone cannot catch this class of
    corruption. The threshold stays at four: real SA IDs can legitimately end in
    one, two or three zeros, so a lower bound would flag valid numbers.
    """
    return len(id13) == 13 and id13.isdigit() and id13.endswith("0000")


def problems(id_number: str, date_of_birth: str) -> list[str]:
    """
    Human-readable reasons an ID number looks wrong; empty when it is fine.

    Cases are checked in order, and only the first structural fault is reported.
    The date-of-birth cross-check (d) fires only when the ID is otherwise sound:

      (a) present but not exactly 13 digits;
      (b) 13 digits but the Appendix B check digit fails;
      (c) 13 digits carrying the Excel scientific-notation signature;
      (d) 13 valid digits whose first six (YYMMDD) do not match the employee's
          date of birth.

    An empty ``id_number`` returns ``[]`` — a missing ID is handled elsewhere
    (it falls back to field 8220).
    """
    if not id_number:
        return []
    if len(id_number) != 13 or not id_number.isdigit():
        return [
            f"ID number {id_number} is not the 13 digits that field 8200 requires"
        ]
    if check_digit_ok(id_number) is False:
        return [f"ID number {id_number} fails the Appendix B check-digit test"]
    if excel_corruption_signature(id_number):
        zeros = len(id_number) - len(id_number.rstrip("0"))
        return [
            f"ID number {id_number} ends in {zeros} zeros — the Excel "
            f"scientific-notation signature"
        ]
    if len(date_of_birth) == 8 and id_number[:6] != date_of_birth[2:8]:
        return [
            f"ID number {id_number}: the first six digits do not match the "
            f"date of birth"
        ]
    return []
