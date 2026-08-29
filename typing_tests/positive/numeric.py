"""``NumericExpect``: a subject whose type is a union, not a parameter.

Chaining has to keep handing back ``NumericExpect`` -- that is the general
``Self`` contract -- but the union is the part worth pinning here. ``int | float``
propagates into everything inherited from ``Expect[T]``: ``.subject`` comes back
as the union whichever built-in went in, and a predicate given to ``matches`` has
to accept both halves. If the subject type is ever widened to cover ordered values
in general, these are the lines that will say so.
"""

from typing import assert_type

from lovely_assertions import NumericExpect, expect


def chaining_keeps_the_numeric_subject(count: int, ratio: float) -> None:
    assert_type(expect(count).is_positive(), NumericExpect)
    assert_type(expect(ratio).is_negative(), NumericExpect)
    assert_type(expect(count).is_greater_than(0).and_.is_less_than(10), NumericExpect)
    assert_type(expect(count).is_greater_than_or_equal_to(0), NumericExpect)
    assert_type(expect(count).is_less_than_or_equal_to(10), NumericExpect)
    assert_type(expect(count).is_zero().and_.is_not_zero(), NumericExpect)
    assert_type(expect(count).is_between(0, 10).and_.is_not_between(20, 30), NumericExpect)
    assert_type(expect(count).is_strictly_between(0, 10), NumericExpect)
    assert_type(expect(ratio).is_close_to(1.0, tol=0.5), NumericExpect)
    assert_type(expect(ratio).is_not_close_to(1.0, tol=0.5), NumericExpect)
    assert_type(expect(ratio).is_nan().and_.is_not_nan(), NumericExpect)
    assert_type(expect(ratio).is_infinite().and_.is_not_infinite(), NumericExpect)


def the_subject_is_the_union(count: int, ratio: float) -> None:
    """Whichever built-in went in, what comes back out is ``int | float``."""
    assert_type(expect(count).is_positive().subject, int | float)
    assert_type(expect(ratio).is_positive().subject, int | float)


def bounds_and_tolerances_take_either_built_in(count: int, ratio: float) -> None:
    """An ``int`` bound on a ``float`` subject and the reverse: both are ``int | float``."""
    expect(ratio).is_between(0, 1)
    expect(count).is_between(0.5, 1.5)
    expect(count).is_greater_than(0.5)
    expect(ratio).is_close_to(1, tol=1)
    expect(count).is_close_to(1.0, tol=0.5)


def predicates_see_the_union(count: int) -> None:
    def is_even(value: int | float) -> bool:
        return value % 2 == 0

    assert_type(expect(count).matches(is_even), NumericExpect)


def because_reaches_the_numeric_assertions(count: int) -> None:
    assert_type(expect(count).is_positive(because="the ledger must balance"), NumericExpect)
    assert_type(expect(count).is_between(0, 10, because="a rating is 0-10"), NumericExpect)
    assert_type(expect(count).is_close_to(9, tol=1, because="drift is allowed"), NumericExpect)
