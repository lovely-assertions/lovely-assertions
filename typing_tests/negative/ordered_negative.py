"""Every marked line here must be rejected by pyright and mypy.

What this rules out: an ordered subject that forgot which type it was ordering, a
bound that let a float slip into a ``Decimal`` comparison, the float-domain
assertions leaking onto a subject that has no float in it, and a type parameter
nobody can compare.
"""

from decimal import Decimal
from typing import Any, assert_type

from lovely_assertions import NumericExpect, expect
from lovely_assertions._ordered import OrderedExpect


# Four classes, each missing one part of the bound. All four operators are named
# on `Ordered` rather than the `__lt__` that sorting alone would need, because a
# NaN makes them independent: `a >= b` is *not* `not (a < b)` when either side is
# unordered. Each omission has to be caught by the checker rather than by a
# `TypeError` in somebody's failing test, so each gets its own line below.
class OnlyLessThan:
    """Enough to sort with, not enough to assert with: ``__lt__`` and nothing else."""

    def __lt__(self, other: Any, /) -> bool:
        return True


class NoLessOrEqual:
    """``is_between`` spells its range ``low <= subject <= high``."""

    def __lt__(self, other: Any, /) -> bool:
        return True

    def __gt__(self, other: Any, /) -> bool:
        return True

    def __ge__(self, other: Any, /) -> bool:
        return True


class NoGreater:
    """``is_greater_than``, ``is_positive`` and the inverted-range guard all call ``>``."""

    def __lt__(self, other: Any, /) -> bool:
        return True

    def __le__(self, other: Any, /) -> bool:
        return True

    def __ge__(self, other: Any, /) -> bool:
        return True


class NoGreaterOrEqual:
    """``is_greater_than_or_equal_to`` calls ``>=``, which ``<`` cannot stand in for."""

    def __lt__(self, other: Any, /) -> bool:
        return True

    def __le__(self, other: Any, /) -> bool:
        return True

    def __gt__(self, other: Any, /) -> bool:
        return True


def the_subject_keeps_its_own_type(price: Decimal) -> None:
    assert_type(OrderedExpect(price).subject, int | float)  # expect-error: it is a `Decimal`
    assert_type(OrderedExpect(price), NumericExpect)  # expect-error: not the built-in subject


def a_bound_has_to_be_the_type_being_ordered(price: Decimal) -> None:
    """The float cases are the point: ``Decimal("0.1") == 0.1`` is false."""
    OrderedExpect(price).is_greater_than(1.5)  # expect-error: a float bound on a `Decimal`
    OrderedExpect(price).is_less_than(0.1)  # expect-error
    OrderedExpect(price).is_between(0.0, 1.0)  # expect-error
    OrderedExpect(price).is_greater_than("2")  # expect-error
    OrderedExpect(price).is_less_than(None)  # expect-error


def a_range_needs_two_bounds(price: Decimal) -> None:
    OrderedExpect(price).is_between(Decimal(1))  # expect-error: one bound is not a range
    OrderedExpect(price).is_strictly_between(Decimal(1))  # expect-error
    OrderedExpect(price).is_not_between()  # expect-error


def because_is_keyword_only(price: Decimal) -> None:
    OrderedExpect(price).is_positive("a reason")  # expect-error: `because` is keyword-only
    OrderedExpect(price).is_greater_than(Decimal(1), "a reason")  # expect-error


def the_sign_assertions_take_no_operand(price: Decimal) -> None:
    OrderedExpect(price).is_zero(Decimal(0))  # expect-error
    OrderedExpect(price).is_not_zero(Decimal(0))  # expect-error


def the_float_domain_assertions_are_not_here(price: Decimal) -> None:
    """``is_nan`` and friends belong to ``NumericExpect``; this subject has no float."""
    OrderedExpect(price).is_nan()  # expect-error
    OrderedExpect(price).is_not_nan()  # expect-error
    OrderedExpect(price).is_infinite()  # expect-error
    OrderedExpect(price).is_close_to(Decimal(1), tol=Decimal(1))  # expect-error


def the_parameter_has_to_be_orderable() -> None:
    OrderedExpect(object())  # expect-error: `object` has no `<`
    OrderedExpect(complex(1, 2))  # expect-error: a complex number is not ordered
    OrderedExpect(None)  # expect-error


def the_numeric_subject_is_not_the_generic_one() -> None:
    """``expect(3)`` is a ``NumericExpect``, not the base it inherits from."""
    assert_type(expect(3), OrderedExpect[int | float])  # expect-error


def every_operator_in_the_bound_is_load_bearing(
    sortable: OnlyLessThan,
    no_le: NoLessOrEqual,
    no_gt: NoGreater,
    no_ge: NoGreaterOrEqual,
) -> None:
    """Dropping any one of the four from ``Ordered`` has to be a static error."""
    OrderedExpect(sortable)  # expect-error: `__le__`, `__gt__` and `__ge__` are required
    OrderedExpect(no_le)  # expect-error: `__le__` is required
    OrderedExpect(no_gt)  # expect-error: `__gt__` is required
    OrderedExpect(no_ge)  # expect-error: `__ge__` is required
