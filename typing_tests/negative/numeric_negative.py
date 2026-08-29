"""Every marked line here must be rejected by pyright and mypy.

What this rules out: a numeric subject that quietly collapsed into ``Expect[int]``,
a tolerance that could be forgotten or passed positionally, and the assumption
that the subject is an ``int`` when it is really ``int | float``.
"""

from decimal import Decimal
from typing import assert_type

from lovely_assertions import Expect, NumericExpect, expect


def the_subject_is_not_an_int(count: int) -> None:
    assert_type(expect(count).subject, int)  # expect-error: the subject is `int | float`
    assert_type(expect(count).is_positive(), Expect[int])  # expect-error: not the base subject


def the_tolerances_are_keyword_only(ratio: float) -> None:
    """Both tolerances default, so `is_close_to(x)` means what `approx(x)` means.

    What is rejected is passing one positionally, so a reader never has to guess
    whether the second argument was absolute or relative.
    """
    expect(ratio).is_close_to(1.0, 0.5)  # expect-error: `tol` is keyword-only
    expect(ratio).is_close_to(1.0, tol="0.5")  # expect-error: a tolerance is a number
    expect(ratio).is_not_close_to(1.0, 0.5)  # expect-error


def a_range_needs_two_numeric_bounds(count: int) -> None:
    expect(count).is_between(1)  # expect-error: one bound is not a range
    expect(count).is_between("1", "5")  # expect-error
    expect(count).is_strictly_between(1)  # expect-error


def comparisons_take_numbers(count: int) -> None:
    expect(count).is_greater_than("3")  # expect-error
    expect(count).is_less_than(None)  # expect-error


def because_is_keyword_only(count: int) -> None:
    expect(count).is_positive("a reason")  # expect-error: `because` is keyword-only
    expect(count).is_greater_than(1, "a reason")  # expect-error


def sign_assertions_take_no_operand(count: int) -> None:
    expect(count).is_zero(0)  # expect-error
    expect(count).is_nan(float("nan"))  # expect-error


def predicates_receive_the_whole_union(count: int) -> None:
    """The predicate sees ``int | float``, so ``int``-only members are out of reach."""
    expect(count).matches(lambda value: value.bit_length() > 2)  # expect-error


def as_cannot_force_a_decimal_into_the_built_in_number_subject(price: Decimal) -> None:
    """``NumericExpect`` holds an ``int | float``, and ``as_`` says so in its signature.

    Declared over ``value: object``, ``as_`` would untie the value from the subject
    entirely: this line would compile, and the mismatch would surface only as a
    ``TypeError`` from inside ``is_close_to`` when the float tolerance met a
    ``Decimal``. ``tests/test_numeric.py`` pins that runtime behaviour, with the value
    laundered on purpose; refusing the ask outright belongs here.
    """
    expect(price, as_=NumericExpect)  # expect-error: a Decimal is not an int | float
