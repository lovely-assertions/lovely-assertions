"""``OrderedExpect``: the ordering catalogue, for anything that compares.

The subject takes any orderable value -- anything answering ``<`` and ``>`` --
and not merely ``int`` and ``float``. That is what carries the comparisons, the
ranges and the sign assertions to a ``Decimal``, which registers with ``numbers``
rather than with the built-ins and would otherwise get the bare generic subject
and an ``AttributeError`` for its trouble.

Two things this file deliberately does *not* cover.

``tests/test_numeric.py`` owns the floating-point edges -- NaN, signed zero,
infinity, unprintable integers, caller-bug ranges and tolerances. Every one of
them belongs to the built-ins, so nothing here duplicates it.

And ``expect()``'s dispatch is wired separately, so the subject is asked for
explicitly here: ``expect(price, as_=OrderedExpect[Decimal])`` rather than
``expect(price)``. The runtime dispatch table lives in
``tests/test_narrowing.py`` and the static one in
``typing_tests/positive/dispatch.py``; both are where the ``Decimal`` row belongs.
"""

import sys
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from types import SimpleNamespace
from typing import Final, NamedTuple

import pytest

from lovely_assertions import (
    AssertionFailure,
    Expect,
    NumericExpect,
    _ordered,
    expect,
    soft_assertions,
)
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._ordered import OrderedExpect, rendered

D1: Final = Decimal(1)
D5: Final = Decimal(5)
D9: Final = Decimal(9)


def _money(amount: str, /) -> OrderedExpect[Decimal]:
    """One ordered subject, for the tables that only care that a reason lands."""
    return expect(Decimal(amount), as_=OrderedExpect[Decimal])


class Version(NamedTuple):
    """Ordered, and emphatically not a number. Used to probe the edge of the subject."""

    major: int
    minor: int


class Loud:
    """A scoped formatter, to prove the ordering messages reach the registry."""

    __slots__ = ()

    def can_handle(self, value: object, /) -> bool:
        return isinstance(value, Decimal)

    def format(self, value: object, /) -> str:
        return str(value) + " EUR"


# ---------------------------------------------------------------------------
# The catalogue reaches every ordered type, not only the built-in numbers
# ---------------------------------------------------------------------------
def test_a_decimal_gets_the_whole_ordering_catalogue() -> None:
    """The assertion this module exists for: ``Decimal`` is an ordered value."""
    subject = expect(Decimal("1.5"), as_=OrderedExpect[Decimal])
    assert subject.is_greater_than(Decimal(1)) is subject
    assert subject.is_greater_than_or_equal_to(Decimal("1.5")) is subject
    assert subject.is_less_than(Decimal(2)) is subject
    assert subject.is_less_than_or_equal_to(Decimal("1.5")) is subject
    assert subject.is_between(Decimal(1), Decimal(2)) is subject
    assert subject.is_not_between(Decimal(3), Decimal(4)) is subject
    assert subject.is_strictly_between(Decimal(1), Decimal(2)) is subject
    assert subject.is_positive() is subject
    assert subject.is_not_zero() is subject


def test_a_fraction_gets_it_too() -> None:
    """``Fraction`` fails ``issubclass(Fraction, int | float)`` for the same reason."""
    subject = expect(Fraction(1, 2), as_=OrderedExpect[Fraction])
    assert subject.is_greater_than(Fraction(1, 3)) is subject
    assert subject.is_between(Fraction(0), Fraction(1)) is subject
    assert subject.is_positive() is subject
    assert subject.is_not_zero() is subject


def test_an_ordering_failure_on_a_decimal_reads_like_any_other() -> None:
    price = Decimal("1.50")
    with pytest.raises(AssertionFailure) as caught:
        expect(price, as_=OrderedExpect[Decimal]).is_greater_than(Decimal("2.00"))
    assert str(caught.value) == (
        "Expected price to be greater than Decimal('2.00'), but was Decimal('1.50')."
    )


def test_a_range_failure_on_a_decimal_names_both_bounds() -> None:
    price = Decimal("9.99")
    with pytest.raises(AssertionFailure) as caught:
        expect(price, as_=OrderedExpect[Decimal]).is_between(Decimal(1), Decimal(5))
    assert str(caught.value) == (
        "Expected price to be between Decimal('1') and Decimal('5') inclusive,"
        " but was Decimal('9.99')."
    )


def test_the_sign_assertions_report_a_decimal() -> None:
    balance = Decimal("-4.00")
    with pytest.raises(AssertionFailure) as caught:
        expect(balance, as_=OrderedExpect[Decimal]).is_positive()
    assert str(caught.value) == "Expected balance to be positive, but was Decimal('-4.00')."


def test_a_negative_decimal_zero_is_zero_and_has_no_sign() -> None:
    """``Decimal("-0")`` is a distinct object from ``Decimal(0)`` and equals it."""
    zero = Decimal("-0")
    assert expect(zero, as_=OrderedExpect[Decimal]).is_zero() is not None
    with pytest.raises(AssertionFailure, match="to be positive"):
        expect(zero, as_=OrderedExpect[Decimal]).is_positive()
    with pytest.raises(AssertionFailure, match="to be negative"):
        expect(zero, as_=OrderedExpect[Decimal]).is_negative()


# ---------------------------------------------------------------------------
# Where a `Decimal` is not a float
# ---------------------------------------------------------------------------
def test_a_decimal_nan_signals_where_a_float_nan_merely_fails() -> None:
    """The one place the two number types genuinely disagree, so it is pinned.

    IEEE 754 lets a comparison against a quiet NaN either answer or signal, and
    the two spellings chose differently: ``float("nan") > 0`` is ``False``, while
    ``Decimal("NaN") > 0`` raises ``InvalidOperation``. That exception propagates
    rather than being turned into an assertion failure -- catching it would mean
    catching ``ArithmeticError``, which is also what a user's own comparable type
    raises when two values are genuinely incomparable, and burying *that* under
    "Expected x to be positive, but was ..." would hide a real bug.
    """
    subject = expect(Decimal("NaN"), as_=OrderedExpect[Decimal])
    with pytest.raises(InvalidOperation):
        subject.is_positive()
    with pytest.raises(InvalidOperation):
        subject.is_greater_than(Decimal(1))
    with pytest.raises(InvalidOperation):
        subject.is_between(Decimal(0), Decimal(2))


def test_the_equality_flavoured_assertions_still_answer_for_a_quiet_decimal_nan() -> None:
    """A *quiet* NaN answers ``==``, so the assertions built on it keep the float meaning."""
    subject = expect(Decimal("NaN"), as_=OrderedExpect[Decimal])
    assert subject.is_not_zero() is subject
    with pytest.raises(AssertionFailure) as caught:
        subject.is_zero()
    assert str(caught.value) == "Expected the value to be zero, but was Decimal('NaN')."


def test_a_signalling_decimal_nan_takes_the_equality_assertions_with_it() -> None:
    """Where ``==`` stops answering too -- pinned as a decision, not left to be found.

    ``Decimal("sNaN")`` is the decimal standard's *signalling* NaN, and it raises
    ``InvalidOperation`` on every operation that examines it, ``==`` and ``!=``
    included. So the zero assertions do not merely fail here the way they do for
    a quiet NaN, and the range guard -- which asks ``value != value`` -- raises
    the arithmetic signal rather than this module's own ``ValueError``.

    Same rule as the ordering case, applied one operator further: a signal raised
    by the value's own arithmetic is a real finding, and repackaging it as
    "Expected x to be zero, but was ..." would bury it.
    """
    signalling = Decimal("sNaN")
    with pytest.raises(InvalidOperation):
        expect(signalling, as_=OrderedExpect[Decimal]).is_zero()
    with pytest.raises(InvalidOperation):
        expect(signalling, as_=OrderedExpect[Decimal]).is_not_zero()
    with pytest.raises(InvalidOperation):
        expect(Decimal(1), as_=OrderedExpect[Decimal]).is_between(signalling, Decimal(5))


def test_a_decimal_nan_bound_is_a_caller_bug_like_a_float_one() -> None:
    """The guard tests ``value != value``, which a ``Decimal`` NaN answers without signalling."""
    with pytest.raises(ValueError, match="NaN"):
        expect(Decimal(1), as_=OrderedExpect[Decimal]).is_between(Decimal("NaN"), Decimal(5))


def test_an_inverted_decimal_range_is_a_caller_bug_like_a_float_one() -> None:
    with pytest.raises(ValueError, match="inverted") as caught:
        expect(Decimal(3), as_=OrderedExpect[Decimal]).is_between(Decimal(5), Decimal(1))
    assert str(caught.value) == ("range is inverted: low Decimal('5') exceeds high Decimal('1')")


# ---------------------------------------------------------------------------
# The edge of the subject
# ---------------------------------------------------------------------------
def test_an_ordered_value_that_is_not_a_number_still_compares() -> None:
    """Comparisons and ranges need only ``<`` and ``>``, so a tuple is fair game."""
    subject = expect(Version(1, 4), as_=OrderedExpect[Version])
    assert subject.is_greater_than(Version(1, 3)) is subject
    assert subject.is_between(Version(1, 0), Version(2, 0)) is subject
    with pytest.raises(AssertionFailure) as caught:
        expect(Version(1, 4), as_=OrderedExpect[Version]).is_less_than(Version(1, 2))
    assert str(caught.value) == (
        "Expected Version(1, 4) to be less than Version(major=1, minor=2),"
        " but was Version(major=1, minor=4)."
    )


def test_the_ordered_subject_has_no_closeness_assertion() -> None:
    """The other half of the line this module draws, and a known gap.

    Closeness needs ``-`` and ``abs``, which the ``Ordered`` protocol does not
    ask for, and a tolerance would have to be typed ``T`` -- a ``Decimal``
    tolerance for a ``Decimal`` subject, since mixing the two number systems is
    what a ``Decimal`` exists to prevent. That is a signature, not an oversight,
    and it is not this subject's: ``NumericExpect.is_close_to`` is ``int | float``
    and the date subjects spell it a third way again (``within=``). So a
    ``Decimal`` gets the whole ordering catalogue and no approximation at all.
    Pinned rather than left to be discovered by an ``AttributeError``.
    """
    subject = expect(Decimal("1.5"), as_=OrderedExpect[Decimal])
    assert not hasattr(subject, "is_close_to")
    assert not hasattr(subject, "is_not_close_to")
    assert not hasattr(expect(Decimal("1.5")), "is_close_to")


def test_the_sign_assertions_have_no_meaning_off_the_number_line() -> None:
    """The known limit of drawing the line here, pinned rather than left to be found.

    ``is_positive`` and its neighbours compare against the literal ``0``, and no
    type system can express "has a zero" -- a protocol that demanded
    ``__gt__(self, other: int)`` would reject ``int`` itself, whose typeshed
    signature takes an ``int`` and not an ``object``. So the rule is a routing
    rule instead: everything ``expect()`` sends to this subject is a number. A
    value asked for by name that is not one gets Python's own answer.
    """
    with pytest.raises(TypeError):
        expect(Version(1, 4), as_=OrderedExpect[Version]).is_positive()
    with pytest.raises(TypeError):
        expect(Version(1, 4), as_=OrderedExpect[Version]).is_negative()


def test_the_zero_assertions_answer_off_the_number_line_rather_than_raising() -> None:
    """The other half of that limit, recorded rather than left to be discovered.

    ``is_zero`` and its negation are spelled with ``==``, which every object
    answers, so off the number line they do not raise the way ``is_positive``
    does: ``is_zero`` reports an ordinary failure and ``is_not_zero`` passes
    without having asserted anything. That asymmetry follows from the routing
    rule -- everything ``expect()`` sends here is a number -- rather than
    licensing the question, and it is pinned so that changing it is a decision.
    """
    release = Version(1, 4)
    assert expect(release, as_=OrderedExpect[Version]).is_not_zero() is not None
    with pytest.raises(AssertionFailure) as caught:
        expect(release, as_=OrderedExpect[Version]).is_zero()
    assert str(caught.value) == "Expected release to be zero, but was Version(major=1, minor=4)."


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def test_an_ordering_message_goes_through_the_formatter_registry() -> None:
    """A domain type gets its registered rendering here, as it does everywhere else."""
    with soft_assertions(formatters=(Loud(),)) as scope:
        price = Decimal("1.50")
        expect(price, as_=OrderedExpect[Decimal]).is_greater_than(Decimal("2.00"))
        collected = scope.discard()
    assert collected == ["Expected price to be greater than 2.00 EUR, but was 1.50 EUR."]


def test_a_rendered_value_is_elided_one_character_past_the_budget() -> None:
    """The legibility threshold, pinned at the boundary rather than well past it.

    ``tests/test_numeric.py`` proves a 201-character integer is elided; that
    leaves the boundary itself -- 120 characters against 121 -- free to drift by
    one in either direction without a test noticing.
    """
    exactly_the_budget = 10**119
    assert len(repr(exactly_the_budget)) == 120
    assert rendered(exactly_the_budget) == repr(exactly_the_budget)

    one_character_over = 10**120
    assert len(repr(one_character_over)) == 121
    assert rendered(one_character_over) == (
        repr(one_character_over)[:120] + "... (truncated from 121 characters)"
    )


def test_the_unprintable_threshold_is_the_estimate_and_not_the_wall() -> None:
    """The hard threshold, pinned at the boundary for the same reason.

    CPython refuses to convert an integer of more than
    ``sys.get_int_max_str_digits()`` digits to text, so past that point the digits
    cannot be produced and the size is all there is to report. The count is an
    *estimate* from ``bit_length`` -- the real one is unobtainable exactly where
    it is needed -- and the comparison is ``>=`` rather than ``>``, so the summary
    starts one digit early rather than one digit late.
    """
    limit = sys.get_int_max_str_digits()
    at_the_limit = 10 ** (limit - 1)
    assert len(str(at_the_limit)) == limit, "the wall this test is about has moved"
    assert rendered(at_the_limit) == "<integer of about " + str(limit) + " digits>"

    one_digit_short = 10 ** (limit - 2)
    assert not rendered(one_digit_short).startswith("<integer of about")
    assert rendered(one_digit_short).endswith(
        "... (truncated from " + str(limit - 1) + " characters)"
    )


# ---------------------------------------------------------------------------
# The subject hierarchy
# ---------------------------------------------------------------------------
def test_the_numeric_subject_is_an_ordered_one() -> None:
    """One ordering catalogue; ``NumericExpect`` is its ``int | float`` half."""
    assert issubclass(NumericExpect, OrderedExpect)
    assert issubclass(OrderedExpect, Expect)
    assert isinstance(expect(3), OrderedExpect)


def test_this_modules_frames_fold_out_of_an_assertion_traceback() -> None:
    """A failing assertion shows the reader's own line, not this module's frames.

    pytest reads ``__tracebackhide__`` from a frame's globals, so one
    module-level assignment folds every frame of ``_ordered.py`` out of a failing
    test's traceback and the reader gets the message rather than a source listing
    of the reporting primitive. It has to be the callable and not ``True``: a
    ``TypeError`` raised inside here -- ``is_positive`` on a value that is not a
    number -- wants those same frames kept, and only a callable can answer the
    two cases differently.
    """
    assert _ordered.__tracebackhide__ is hide_internal_frames
    assert hide_internal_frames(SimpleNamespace(value=AssertionFailure("x"))) is True
    assert hide_internal_frames(SimpleNamespace(value=TypeError("x"))) is False


def test_the_ordered_subject_carries_no_instance_dictionary() -> None:
    """Every subject in the library is ``__slots__``-ed, this one included."""
    assert OrderedExpect.__slots__ == ()
    assert not hasattr(OrderedExpect(Decimal(1)), "__dict__")


def test_every_assertion_hands_back_the_same_subject() -> None:
    subject = expect(Decimal("1.5"), as_=OrderedExpect[Decimal])
    chained = subject.is_positive().and_.is_between(Decimal(1), Decimal(2)).and_.is_not_zero()
    assert chained is subject


# ---------------------------------------------------------------------------
# The happy path and `because`
# ---------------------------------------------------------------------------
def test_passing_ordered_assertions_never_touch_the_failure_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A passing assertion never reaches the failure path, argument checks and all.

    ``tests/test_happy_path.py`` owns the general form of this guard. The ranges
    get their own because they do work *before* the comparison, which is the
    obvious place to start building a message by accident.
    """

    def detonate(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("a passing assertion reached the failure path")

    monkeypatch.setattr(Expect, "_fail", detonate)
    subject = expect(Decimal("1.5"), as_=OrderedExpect[Decimal])
    subject.is_greater_than(Decimal(1)).and_.is_less_than_or_equal_to(Decimal(2))
    subject.is_between(Decimal(1), Decimal(2)).and_.is_strictly_between(Decimal(1), Decimal(2))
    subject.is_positive().and_.is_not_zero()


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda: _money("1").is_greater_than(D9, because="R"), id="is_greater_than"),
        pytest.param(
            lambda: _money("1").is_greater_than_or_equal_to(D9, because="R"),
            id="is_greater_or_equal",
        ),
        pytest.param(lambda: _money("9").is_less_than(D1, because="R"), id="is_less_than"),
        pytest.param(
            lambda: _money("9").is_less_than_or_equal_to(D1, because="R"), id="is_less_or_equal"
        ),
        pytest.param(lambda: _money("-1").is_positive(because="R"), id="is_positive"),
        pytest.param(lambda: _money("1").is_negative(because="R"), id="is_negative"),
        pytest.param(lambda: _money("1").is_zero(because="R"), id="is_zero"),
        pytest.param(lambda: _money("0").is_not_zero(because="R"), id="is_not_zero"),
        pytest.param(lambda: _money("9").is_between(D1, D5, because="R"), id="is_between"),
        pytest.param(lambda: _money("3").is_not_between(D1, D5, because="R"), id="is_not_between"),
        pytest.param(
            lambda: _money("5").is_strictly_between(D1, D5, because="R"), id="is_strictly_between"
        ),
    ],
)
def test_because_reaches_every_ordered_assertion(call: Callable[[], object]) -> None:
    with pytest.raises(AssertionFailure, match="because R"):
        call()
