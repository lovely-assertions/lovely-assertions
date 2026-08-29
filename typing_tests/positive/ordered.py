"""``OrderedExpect[T]``: one catalogue, parameterised by what is being ordered.

``numeric.py`` pins the ``int | float`` half; this file pins the half the type
parameter exists for. Three properties matter:

* ``T`` survives every assertion, so ``.subject`` comes back as the type that went
  in -- a ``Decimal`` stays a ``Decimal`` and does not widen to ``int | float``;
* the operand of a comparison is ``T`` as well, which is what keeps a float bound
  out of a ``Decimal`` comparison (``Decimal("0.1") == 0.1`` is false, and an
  assertion library that let that through would be undermining the reason the
  value is a ``Decimal``). ``ordered_negative.py`` holds that half;
* the bound is structural, so a user's own comparable type is a subject without
  registering anything.

``expect()``'s ``Decimal`` and ``Fraction`` overloads are pinned in
``dispatch.py``, with the rest of the dispatch table; the subject is constructed
or asked for by name here.
"""

from decimal import Decimal
from fractions import Fraction
from typing import NamedTuple, assert_type

from lovely_assertions import expect
from lovely_assertions._ordered import OrderedExpect


class Version(NamedTuple):
    """Ordered by the tuple ordering it inherits, and not a number."""

    major: int
    minor: int


def chaining_keeps_the_parameterised_subject(price: Decimal) -> None:
    subject = OrderedExpect(price)
    assert_type(subject, OrderedExpect[Decimal])
    assert_type(subject.is_greater_than(Decimal(1)), OrderedExpect[Decimal])
    assert_type(subject.is_greater_than_or_equal_to(Decimal(1)), OrderedExpect[Decimal])
    assert_type(subject.is_less_than(Decimal(9)), OrderedExpect[Decimal])
    assert_type(subject.is_less_than_or_equal_to(Decimal(9)), OrderedExpect[Decimal])
    assert_type(subject.is_positive().and_.is_negative(), OrderedExpect[Decimal])
    assert_type(subject.is_zero().and_.is_not_zero(), OrderedExpect[Decimal])
    assert_type(subject.is_between(Decimal(1), Decimal(9)), OrderedExpect[Decimal])
    assert_type(subject.is_not_between(Decimal(1), Decimal(9)), OrderedExpect[Decimal])
    assert_type(subject.is_strictly_between(Decimal(1), Decimal(9)), OrderedExpect[Decimal])


def the_subject_keeps_its_own_type(price: Decimal, ratio: Fraction) -> None:
    """The whole point of the parameter: a ``Decimal`` does not widen to a union."""
    assert_type(OrderedExpect(price).is_positive().subject, Decimal)
    assert_type(OrderedExpect(ratio).is_positive().subject, Fraction)


def the_explicit_subject_form_is_typed(price: Decimal) -> None:
    """``as_=`` is the fully typed way to ask for a subject by name."""
    assert_type(expect(price, as_=OrderedExpect[Decimal]), OrderedExpect[Decimal])
    assert_type(
        expect(price, as_=OrderedExpect[Decimal]).is_greater_than(Decimal(1)),
        OrderedExpect[Decimal],
    )


def a_user_defined_comparable_type_is_a_subject(release: Version) -> None:
    """The bound is structural: nothing had to be registered for this to typecheck."""
    assert_type(OrderedExpect(release).is_greater_than(Version(1, 0)), OrderedExpect[Version])
    assert_type(
        OrderedExpect(release).is_between(Version(1, 0), Version(2, 0)), OrderedExpect[Version]
    )
    assert_type(OrderedExpect(release).subject, Version)


def strings_and_tuples_are_ordered_too(word: str, point: tuple[int, int]) -> None:
    """Not types ``expect()`` routes here, but the bound must not reject them."""
    assert_type(OrderedExpect(word).is_less_than("z"), OrderedExpect[str])
    assert_type(OrderedExpect(point).is_greater_than((0, 0)), OrderedExpect[tuple[int, int]])


def because_reaches_the_ordered_assertions(price: Decimal) -> None:
    subject = OrderedExpect(price)
    assert_type(subject.is_positive(because="an invoice is never negative"), OrderedExpect[Decimal])
    assert_type(
        subject.is_between(Decimal(1), Decimal(9), because="the band is 1-9"),
        OrderedExpect[Decimal],
    )
    assert_type(subject.is_greater_than(Decimal(1), because="R"), OrderedExpect[Decimal])


def the_inherited_catalogue_still_sees_the_parameter(price: Decimal) -> None:
    """``OrderedExpect[T]`` is an ``Expect[T]``, so ``matches`` gets a ``Decimal``."""

    def is_round(value: Decimal) -> bool:
        return value == value.to_integral_value()

    assert_type(OrderedExpect(price).matches(is_round), OrderedExpect[Decimal])
    assert_type(OrderedExpect(price).is_equal_to(Decimal(1)), OrderedExpect[Decimal])
