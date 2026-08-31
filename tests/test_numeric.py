"""``NumericExpect``, and the floating-point edges it has to get right.

The ordinary comparisons are quick. Most of this file is the part that numeric
assertion libraries get wrong: NaN, signed zero, infinity, and the caller bugs --
an inverted range, a negative tolerance -- that must raise ``ValueError`` instead
of reporting an assertion failure the subject never caused.

The comparisons, the ranges and the sign assertions are inherited from
``OrderedExpect``, which is what lets a ``Decimal`` reach them too
(``tests/test_ordered.py``). They are exercised here rather than there because
every edge that makes them hard -- an unordered NaN, a signed zero, an integer
too long to print -- belongs to the built-ins and to no other ordered type.
"""

import sys
from collections.abc import Callable
from decimal import Decimal
from fractions import Fraction
from typing import Any, Final

import pytest

from lovely_assertions import AssertionFailure, Expect, NumericExpect, expect

NAN: Final = float("nan")
INF: Final = float("inf")


def as_number(value: object, /) -> Any:
    """Hand a non-built-in number to a signature typed ``int | float``.

    ``Decimal`` and ``Fraction`` register with ``numbers`` rather than with the
    built-ins, so both checkers reject them as an operand here -- correctly, and
    that rejection is half of what the tests below are about. The other half is
    what the *runtime* does when the rejection is ignored, which cannot be
    written down without laundering the value. One helper rather than a
    suppression per line, so the deliberateness is visible.
    """
    return value


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------
def test_ordering_passes_and_chains() -> None:
    subject = expect(5)
    assert subject.is_greater_than(4) is subject
    assert subject.is_greater_than_or_equal_to(5) is subject
    assert subject.is_less_than(6) is subject
    assert subject.is_less_than_or_equal_to(5) is subject


def test_is_greater_than_reports_both_sides() -> None:
    count = 2
    with pytest.raises(AssertionFailure) as caught:
        expect(count).is_greater_than(3)
    assert str(caught.value) == "Expected count to be greater than 3, but was 2."


def test_is_greater_than_excludes_equality_but_its_relaxed_form_does_not() -> None:
    with pytest.raises(AssertionFailure, match="to be greater than 5"):
        expect(5).is_greater_than(5)
    expect(5).is_greater_than_or_equal_to(5)


def test_is_greater_than_or_equal_to_reports_both_sides() -> None:
    count = 2
    with pytest.raises(AssertionFailure) as caught:
        expect(count).is_greater_than_or_equal_to(3)
    assert str(caught.value) == "Expected count to be greater than or equal to 3, but was 2."


def test_is_less_than_reports_both_sides() -> None:
    ratio = 2.5
    with pytest.raises(AssertionFailure) as caught:
        expect(ratio).is_less_than(1.0)
    assert str(caught.value) == "Expected ratio to be less than 1.0, but was 2.5."


def test_is_less_than_excludes_equality_but_its_relaxed_form_does_not() -> None:
    with pytest.raises(AssertionFailure, match="to be less than 5"):
        expect(5).is_less_than(5)
    expect(5).is_less_than_or_equal_to(5)


def test_is_less_than_or_equal_to_reports_both_sides() -> None:
    ratio = 2.5
    with pytest.raises(AssertionFailure) as caught:
        expect(ratio).is_less_than_or_equal_to(1.0)
    assert str(caught.value) == "Expected ratio to be less than or equal to 1.0, but was 2.5."


def test_an_ordering_against_a_nan_says_why_it_failed() -> None:
    """``to be greater than nan, but was 5`` reads like the library misfired.

    The subject is right there and nothing looks wrong with it, so the message
    names the operand as the reason rather than leaving the reader to remember
    that every ordering against a NaN is false.
    """
    note = " (a NaN compares false against every ordering)."
    limit = NAN

    with pytest.raises(AssertionFailure) as caught:
        expect(5).is_greater_than(limit)
    assert str(caught.value) == "Expected 5 to be greater than nan, but was 5" + note

    with pytest.raises(AssertionFailure) as caught:
        expect(5).is_greater_than_or_equal_to(limit)
    assert str(caught.value) == "Expected 5 to be greater than or equal to nan, but was 5" + note

    with pytest.raises(AssertionFailure) as caught:
        expect(5).is_less_than(limit)
    assert str(caught.value) == "Expected 5 to be less than nan, but was 5" + note

    with pytest.raises(AssertionFailure) as caught:
        expect(5).is_less_than_or_equal_to(limit)
    assert str(caught.value) == "Expected 5 to be less than or equal to nan, but was 5" + note


def test_an_ordering_that_a_nan_did_not_doom_carries_no_note() -> None:
    """The note is for the counter-intuitive case only; it must not follow every failure."""
    count = 2
    with pytest.raises(AssertionFailure) as caught:
        expect(count).is_greater_than(3)
    assert "NaN" not in str(caught.value)


def test_ints_and_floats_compare_against_each_other() -> None:
    expect(3).is_greater_than(2.5)
    expect(2.5).is_less_than(3)


# ---------------------------------------------------------------------------
# Sign and zero
# ---------------------------------------------------------------------------
def test_is_positive_and_is_negative() -> None:
    expect(1).is_positive()
    expect(-1.5).is_negative()


def test_is_positive_reports_the_value() -> None:
    balance = -4
    with pytest.raises(AssertionFailure) as caught:
        expect(balance).is_positive()
    assert str(caught.value) == "Expected balance to be positive, but was -4."


def test_is_negative_reports_the_value() -> None:
    balance = 4
    with pytest.raises(AssertionFailure) as caught:
        expect(balance).is_negative()
    assert str(caught.value) == "Expected balance to be negative, but was 4."


@pytest.mark.parametrize("zero", [0, 0.0, -0.0])
def test_zero_has_no_sign_not_even_a_negative_one(zero: int | float) -> None:
    """``-0.0 == 0``, so the sign bit does not make it a negative number."""
    expect(zero).is_zero()
    with pytest.raises(AssertionFailure, match="to be positive"):
        expect(zero).is_positive()
    with pytest.raises(AssertionFailure, match="to be negative"):
        expect(zero).is_negative()


def test_is_zero_reports_the_value() -> None:
    balance = 3
    with pytest.raises(AssertionFailure) as caught:
        expect(balance).is_zero()
    assert str(caught.value) == "Expected balance to be zero, but was 3."


def test_is_not_zero() -> None:
    expect(3).is_not_zero()
    balance = 0.0
    with pytest.raises(AssertionFailure) as caught:
        expect(balance).is_not_zero()
    assert str(caught.value) == "Expected balance not to be zero, but it was."


# ---------------------------------------------------------------------------
# Ranges: `is_between` includes its bounds
# ---------------------------------------------------------------------------
def test_is_between_includes_both_bounds() -> None:
    expect(1).is_between(1, 5)
    expect(3).is_between(1, 5)
    expect(5).is_between(1, 5)


def test_is_between_reports_the_range() -> None:
    age = 7
    with pytest.raises(AssertionFailure) as caught:
        expect(age).is_between(1, 5)
    assert str(caught.value) == "Expected age to be between 1 and 5 inclusive, but was 7."


def test_is_not_between_is_the_complement_of_is_between() -> None:
    expect(7).is_not_between(1, 5)
    age = 3
    with pytest.raises(AssertionFailure) as caught:
        expect(age).is_not_between(1, 5)
    assert str(caught.value) == "Expected age not to be between 1 and 5 inclusive, but was 3."


def test_is_strictly_between_excludes_both_bounds() -> None:
    expect(3).is_strictly_between(1, 5)
    edge = 5
    with pytest.raises(AssertionFailure) as caught:
        expect(edge).is_strictly_between(1, 5)
    assert str(caught.value) == "Expected edge to be strictly between 1 and 5, but was 5."


def test_an_inverted_range_is_a_caller_bug() -> None:
    """Nothing satisfies ``5..1``, so failing the subject would blame the wrong party."""
    with pytest.raises(ValueError, match="inverted"):
        expect(3).is_between(5, 1)
    with pytest.raises(ValueError, match="inverted"):
        expect(3).is_not_between(5, 1)
    with pytest.raises(ValueError, match="inverted"):
        expect(3).is_strictly_between(5, 1)


def test_a_single_point_is_a_range_but_an_empty_exclusive_one_is_a_caller_bug() -> None:
    expect(3).is_between(3, 3)
    with pytest.raises(ValueError, match="empty"):
        expect(3).is_strictly_between(3, 3)


def test_the_empty_exclusive_range_names_both_bounds() -> None:
    """``-0.0 == 0.0``, so the two bounds can be equal without looking the same."""
    with pytest.raises(ValueError, match="empty") as caught:
        expect(0).is_strictly_between(-0.0, 0.0)
    assert str(caught.value) == "exclusive range is empty: low -0.0 equals high 0.0"


def test_a_nan_bound_is_a_caller_bug() -> None:
    """A NaN bound orders against nothing; no subject could ever be inside it."""
    with pytest.raises(ValueError, match="NaN"):
        expect(3).is_between(NAN, 5)
    with pytest.raises(ValueError, match="NaN"):
        expect(3).is_between(1, NAN)
    with pytest.raises(ValueError, match="NaN"):
        expect(3).is_not_between(NAN, NAN)
    with pytest.raises(ValueError, match="NaN"):
        expect(3).is_strictly_between(1, NAN)


def test_the_range_is_validated_before_the_subject_is_looked_at() -> None:
    """Otherwise a subject that happened to fail would hide the caller's bug."""
    with pytest.raises(ValueError, match="inverted"):
        expect(99).is_between(5, 1)


# ---------------------------------------------------------------------------
# Approximation
# ---------------------------------------------------------------------------
def test_is_close_to_uses_an_absolute_tolerance() -> None:
    expect(10.25).is_close_to(10.0, tol=0.25)
    expect(9.75).is_close_to(10.0, tol=0.25)
    expect(10.0).is_close_to(10.0, tol=0.0)
    with pytest.raises(AssertionFailure, match="to be within"):
        expect(10.5).is_close_to(10.0, tol=0.25)


def test_the_tolerance_does_not_scale_with_magnitude() -> None:
    """Absolute, not relative: ``tol`` means the same at any size of number."""
    expect(1000000.25).is_close_to(1000000.0, tol=0.5)
    with pytest.raises(AssertionFailure, match="to be within"):
        expect(0.75).is_close_to(0.0, tol=0.5)


def test_is_close_to_reports_the_distance() -> None:
    ratio = 10.5
    with pytest.raises(AssertionFailure) as caught:
        expect(ratio).is_close_to(10.0, tol=0.25)
    assert str(caught.value) == "Expected ratio to be within 0.25 of 10.0, but 10.5 was 0.5 away."


def test_is_not_close_to_reports_how_close_it_was() -> None:
    expect(11.0).is_not_close_to(10.0, tol=0.25)
    ratio = 10.125
    with pytest.raises(AssertionFailure) as caught:
        expect(ratio).is_not_close_to(10.0, tol=0.25)
    assert str(caught.value) == (
        "Expected ratio not to be within 0.25 of 10.0, but was 10.125, only 0.125 away."
    )


def test_is_not_close_to_reports_an_exact_match_as_one() -> None:
    """There is no gap to measure, so the message does not pretend to measure one.

    For two infinities there is no subtraction either -- ``inf - inf`` is a NaN,
    not a distance of zero -- and reporting ``nan away`` would be worse than
    saying nothing.
    """
    ratio = 10.0
    with pytest.raises(AssertionFailure) as caught:
        expect(ratio).is_not_close_to(10.0, tol=0.25)
    assert str(caught.value) == "Expected ratio not to be within 0.25 of 10.0, but was equal to it."

    reading = INF
    with pytest.raises(AssertionFailure) as caught:
        expect(reading).is_not_close_to(INF, tol=0.0)
    assert str(caught.value) == "Expected reading not to be within 0.0 of inf, but was equal to it."


@pytest.mark.parametrize("tol", [-0.25, -1, NAN])
def test_an_unusable_tolerance_is_a_caller_bug(tol: int | float) -> None:
    """A negative or NaN tolerance describes no neighbourhood; that is a test bug.

    Validated before the comparison, so even a subject that would trivially pass
    (``value`` against itself) still reports the bug.
    """
    with pytest.raises(ValueError, match="tolerance must not be"):
        expect(1.0).is_close_to(1.0, tol=tol)
    with pytest.raises(ValueError, match="tolerance must not be"):
        expect(1.0).is_not_close_to(1.0, tol=tol)


def test_an_infinite_tolerance_is_allowed() -> None:
    """Unlike a negative one, it is satisfiable -- by every pair of real numbers."""
    expect(1.0).is_close_to(1e308, tol=INF)


# ---------------------------------------------------------------------------
# Relative tolerance
# ---------------------------------------------------------------------------
def test_naming_no_tolerance_means_what_pytest_approx_means() -> None:
    """``is_close_to(x)`` is ``x == pytest.approx(x)``: relative 1e-6, floored at 1e-12.

    The reflex every Python developer already has is ``pytest.approx(x)`` with no
    argument, and a library that spelled the same call differently -- or refused
    it -- would be teaching a second answer to a question that already has one.
    """
    expect(1000000.5).is_close_to(1000000.0)
    expect(2.0000001).is_close_to(2.0)
    with pytest.raises(AssertionFailure, match="to be within"):
        expect(2.5).is_close_to(2.0)


def test_the_default_is_floored_so_it_still_works_at_zero() -> None:
    """A purely relative tolerance is worthless at zero: ``rel * 0`` is ``0``.

    Without the floor ``is_close_to(0.0)`` would be an equality test wearing an
    approximation's name -- which is exactly why ``pytest.approx`` has the floor,
    and why copying the relative default without it would have been worse than
    having no default at all.
    """
    expect(0.0).is_close_to(0.0)
    expect(1e-13).is_close_to(0.0)
    with pytest.raises(AssertionFailure, match="to be within"):
        expect(1e-11).is_close_to(0.0)


def test_a_relative_tolerance_scales_with_the_target() -> None:
    """The whole point of ``rel``: one part in a thousand means more at a million."""
    expect(1000100.0).is_close_to(1000000.0, rel=1e-3)
    expect(1.0009).is_close_to(1.0, rel=1e-3)
    with pytest.raises(AssertionFailure, match="to be within"):
        expect(1.01).is_close_to(1.0, rel=1e-3)


def test_an_absolute_tolerance_alone_is_unchanged_and_unfloored() -> None:
    """``tol=`` short-circuits: naming it asks for that band and nothing else.

    In particular it picks up no floor. ``tol=0.0`` is an exact-equality
    tolerance and stays one; a floor slipped under it would silently widen every
    assertion already written against this library.
    """
    expect(1e-13).is_close_to(0.0, tol=1e-12)
    with pytest.raises(AssertionFailure, match="to be within"):
        expect(1e-13).is_close_to(0.0, tol=0.0)


def test_both_tolerances_mean_within_either_one() -> None:
    """``pytest.approx``'s rule, and the only reading that earns the second argument.

    Within *both* is the narrower of the two, which the caller could always have
    written as a single ``tol``. Within either is the combination nothing else
    expresses: a relative band for large values, an absolute floor for small
    ones.
    """
    # The absolute one carries it: 1e-9 of 0.0 is nothing at all.
    expect(0.5).is_close_to(0.0, tol=1.0, rel=1e-9)
    # The relative one carries it: 1.0 absolute would not reach 100.
    expect(1000100.0).is_close_to(1000000.0, tol=1.0, rel=1e-3)
    with pytest.raises(AssertionFailure, match="to be within"):
        expect(5.0).is_close_to(0.0, tol=1.0, rel=1e-9)


def test_tol_zero_with_rel_is_the_pure_relative_escape_hatch() -> None:
    """ "Within either" makes ``tol=0`` the way to ask for no floor at all."""
    with pytest.raises(AssertionFailure, match="to be within"):
        expect(1e-13).is_close_to(0.0, rel=1e-6, tol=0)


def test_an_infinite_relative_tolerance_covers_everything() -> None:
    """A tolerance the caller asked to be infinite stays infinite, as ``tol=inf`` does.

    The zero target is the case that needs the guard rather than the arithmetic:
    ``inf * 0.0`` is a NaN, and a NaN band loses to the floor, so an infinity
    multiplied out would end up the *narrowest* tolerance on offer instead of the
    widest.
    """
    expect(0.0).is_close_to(10.0, rel=INF)
    expect(1.0).is_close_to(0.0, rel=INF)
    expect(-1e300).is_close_to(0.0, rel=INF)


def test_an_infinite_target_has_no_relative_neighbourhood() -> None:
    """``rel * inf`` is ``inf``, and a band of ``inf`` would pass everything.

    That would be the vacuous assertion this library refuses elsewhere, so an
    infinite target contributes no relative band at all: nothing is close to an
    infinity but the same infinity, by the equality tested before the
    subtraction. ``tol=inf`` remains the way to say "everything is close".
    """
    expect(INF).is_close_to(INF)
    expect(-INF).is_close_to(-INF)
    with pytest.raises(AssertionFailure, match="to be within"):
        expect(0.0).is_close_to(INF)
    with pytest.raises(AssertionFailure, match="to be within"):
        expect(INF).is_close_to(-INF)
    expect(0.0).is_not_close_to(INF)


def test_a_nan_target_still_has_no_neighbourhood_by_default() -> None:
    """``rel * nan`` is a NaN, which is not a band either. The floor decides, and fails.

    The message is pinned whole because the tolerance gloss has to survive on
    *this* branch too: it is the one that reports no distance, so it is the one
    where a reader most needs to know which band was asked for.
    """
    reading = 1.0
    with pytest.raises(AssertionFailure) as caught:
        expect(reading).is_close_to(NAN)
    assert str(caught.value) == (
        "Expected reading to be within 1e-12 of nan"
        " (the default relative tolerance of 1e-06, floored at 1e-12),"
        " but was 1.0 (a NaN is close to nothing, itself included)."
    )
    with pytest.raises(AssertionFailure) as caught:
        expect(reading).is_close_to(NAN, rel=1e-3)
    assert "(a relative tolerance of 0.001, floored at 1e-12)" in str(caught.value)
    expect(1.0).is_not_close_to(NAN)


def test_a_nan_is_close_to_nothing_even_at_an_infinite_tolerance() -> None:
    """``tol=inf`` covers every real gap, and a NaN is not a real gap.

    The measurable path says so by arithmetic -- ``abs(1.0 - nan)`` is a NaN and
    ``nan <= inf`` is false. The path with no measurable distance has to agree
    rather than read an infinite tolerance as "close to anything", or a subject
    too large for a float would become the one subject a NaN *is* close to.
    """
    with pytest.raises(AssertionFailure, match="a NaN is close to nothing"):
        expect(1.0).is_close_to(NAN, tol=INF)
    with pytest.raises(AssertionFailure, match="a NaN is close to nothing"):
        expect(10**5000).is_close_to(NAN, tol=INF)
    with pytest.raises(AssertionFailure, match="a NaN is close to nothing"):
        expect(NAN).is_close_to(10**5000, tol=INF)
    expect(10**5000).is_not_close_to(NAN, tol=INF)
    expect(NAN).is_not_close_to(10**5000, tol=INF)


def test_is_not_close_to_takes_the_same_tolerances() -> None:
    """The complement, argument for argument -- not a second set of rules."""
    expect(2.5).is_not_close_to(2.0)
    expect(1.01).is_not_close_to(1.0, rel=1e-3)
    expect(5.0).is_not_close_to(0.0, tol=1.0, rel=1e-9)
    with pytest.raises(AssertionFailure, match="not to be within"):
        expect(1000100.0).is_not_close_to(1000000.0, rel=1e-3)


@pytest.mark.parametrize("rel", [-0.25, -1, NAN])
def test_an_unusable_relative_tolerance_is_a_caller_bug(rel: int | float) -> None:
    """``rel`` is validated exactly as ``tol`` is, and the message says which one."""
    with pytest.raises(ValueError, match="relative tolerance must not be"):
        expect(1.0).is_close_to(1.0, rel=rel)
    with pytest.raises(ValueError, match="relative tolerance must not be"):
        expect(1.0).is_not_close_to(1.0, rel=rel)


# ---------------------------------------------------------------------------
# What a closeness failure says about the tolerance it used
# ---------------------------------------------------------------------------
def test_the_default_tolerance_is_named_rather_than_left_to_be_guessed() -> None:
    """A number the caller never typed appears in the message, so it says where from."""
    ratio = 2.5
    with pytest.raises(AssertionFailure) as caught:
        expect(ratio).is_close_to(2.0)
    assert str(caught.value) == (
        "Expected ratio to be within 2e-06 of 2.0"
        " (the default relative tolerance of 1e-06), but 2.5 was 0.5 away."
    )


def test_a_relative_tolerance_is_named_and_the_band_it_came_to_is_reported() -> None:
    """The band leads, in the same units as the distance, so the reader can subtract."""
    ratio = 2.5
    with pytest.raises(AssertionFailure) as caught:
        expect(ratio).is_close_to(2.0, rel=1e-3)
    assert str(caught.value) == (
        "Expected ratio to be within 0.002 of 2.0"
        " (a relative tolerance of 0.001), but 2.5 was 0.5 away."
    )


def test_both_tolerances_are_named_and_the_wider_one_is_the_band() -> None:
    ratio = 2.5
    with pytest.raises(AssertionFailure) as caught:
        expect(ratio).is_close_to(2.0, tol=0.1, rel=1e-3)
    assert str(caught.value) == (
        "Expected ratio to be within 0.1 of 2.0"
        " (the wider of an absolute 0.1 and a relative 0.001), but 2.5 was 0.5 away."
    )


def test_the_floor_is_named_only_when_the_floor_set_the_band() -> None:
    """1e-12 in a message nobody wrote 1e-12 in needs an explanation; elsewhere it is noise."""
    reading = 1e-11
    with pytest.raises(AssertionFailure) as caught:
        expect(reading).is_close_to(0.0)
    assert str(caught.value) == (
        "Expected reading to be within 1e-12 of 0.0"
        " (the default relative tolerance of 1e-06, floored at 1e-12),"
        " but 1e-11 was 1e-11 away."
    )
    with pytest.raises(AssertionFailure) as caught:
        expect(reading).is_close_to(2.0)
    assert "floored" not in str(caught.value)


def test_a_bare_absolute_tolerance_gets_no_gloss() -> None:
    """The one call where the number in the message is the number in the call.

    Every other spelling derives its band from something the caller never typed,
    so it says where the number came from. The absolute form has nothing to
    explain and carries no parenthetical at all.
    """
    ratio = 2.5
    with pytest.raises(AssertionFailure) as caught:
        expect(ratio).is_close_to(2.0, tol=0.1)
    assert str(caught.value) == "Expected ratio to be within 0.1 of 2.0, but 2.5 was 0.5 away."


def test_the_band_is_reported_exactly_rather_than_rounded() -> None:
    """``1e-6 * 10.0`` is not ``1e-05``, and the message does not pretend it is.

    ``pytest.approx`` prints its tolerance to one significant figure. This is the
    deliberate divergence: the round number the caller thinks in is already in
    the parenthetical, so the leading number can afford to be the one the
    comparison actually used -- and a reader checking a borderline result against
    the message gets an answer that reproduces.
    """
    ratio = 10.5
    with pytest.raises(AssertionFailure) as caught:
        expect(ratio).is_close_to(10.0)
    assert str(caught.value) == (
        "Expected ratio to be within 9.999999999999999e-06 of 10.0"
        " (the default relative tolerance of 1e-06), but 10.5 was 0.5 away."
    )


def test_is_not_close_to_names_the_tolerance_too() -> None:
    ratio = 1000100.0
    with pytest.raises(AssertionFailure) as caught:
        expect(ratio).is_not_close_to(1000000.0, rel=1e-3)
    assert str(caught.value) == (
        "Expected ratio not to be within 1000.0 of 1000000.0"
        " (a relative tolerance of 0.001), but was 1000100.0, only 100.0 away."
    )


def test_every_branch_of_is_not_close_to_names_the_tolerance() -> None:
    """Three failure branches, three chances to drop the gloss and never notice.

    The equal branch has no distance to report and the unmeasurable one has no
    distance to measure, so on both of them the band is the only number the
    reader gets -- which makes them the two that most need to say where it came
    from.
    """
    reading = 1.0
    with pytest.raises(AssertionFailure) as caught:
        expect(reading).is_not_close_to(1.0)
    assert str(caught.value) == (
        "Expected reading not to be within 1e-06 of 1.0"
        " (the default relative tolerance of 1e-06), but was equal to it."
    )
    with pytest.raises(AssertionFailure) as caught:
        expect(reading).is_not_close_to(1.0, tol=0.5, rel=1e-3)
    assert str(caught.value) == (
        "Expected reading not to be within 0.5 of 1.0"
        " (the wider of an absolute 0.5 and a relative 0.001), but was equal to it."
    )
    with pytest.raises(AssertionFailure) as caught:
        expect(reading).is_not_close_to(10**5000, rel=INF)
    assert str(caught.value) == (
        "Expected reading not to be within inf of <integer of about 5001 digits>"
        " (a relative tolerance of inf), but was 1.0."
    )


def test_a_relative_band_no_float_can_hold_is_still_a_band() -> None:
    """``1e-6 * 10**5000`` overflows a float; the band is exact integer arithmetic.

    Returning an infinity instead would have made every value close to a large
    enough target, which is the vacuous pass this library exists to prevent.
    """
    reading = 1.0
    with pytest.raises(AssertionFailure) as caught:
        expect(reading).is_close_to(10**5000)
    assert str(caught.value) == (
        "Expected reading to be within <integer of about 4995 digits>"
        " of <integer of about 5001 digits>"
        " (the default relative tolerance of 1e-06),"
        " but was 1.0, further from it than any float can measure."
    )


def test_a_relative_tolerance_no_float_can_hold_is_a_band_too() -> None:
    """The overflow stands on both sides of the multiplication, not just the target's.

    ``1e-6 * 10**5000`` overflows on the magnitude and ``10**5000 * 2.0``
    overflows on the tolerance, for the same reason: either operand converts the
    other to a float first. Both have to be carried exactly, or a ``rel`` too
    large for a float raises ``OverflowError`` out of an assertion that had a
    verdict to give.
    """
    expect(3.0).is_close_to(2.0, rel=10**5000)
    expect(3).is_close_to(2, rel=10**5000)
    with pytest.raises(AssertionFailure, match="not to be within"):
        expect(3.0).is_not_close_to(2.0, rel=10**5000)
    with pytest.raises(AssertionFailure, match="a NaN is close to nothing"):
        expect(3.0).is_close_to(NAN, rel=10**5000)


def test_a_gap_no_float_can_measure_is_still_decided_rather_than_declined() -> None:
    """The band can be wider than a gap that no float can hold, and then it holds.

    "Close only if the tolerance is infinite" would be defensible if every
    tolerance were a number the caller typed. ``rel`` derives one from the
    target, so against a target this large the derived band is that large too,
    and the shortcut would print a band visibly wider than the gap while calling
    the value too far away -- a message contradicting itself.
    """
    expect(1.0).is_close_to(10**5000, rel=2)
    expect(1.0).is_close_to(10**5000, tol=2 * 10**5000)
    expect(10**5000).is_close_to(0.0, tol=10**5001)
    with pytest.raises(AssertionFailure, match="not to be within"):
        expect(1.0).is_not_close_to(10**5000, rel=2)
    # Still a real verdict on the other side of the boundary.
    with pytest.raises(AssertionFailure, match="further from it than any float can measure"):
        expect(1.0).is_close_to(10**5000, rel=0.5)
    expect(1.0).is_not_close_to(10**5000, rel=0.5)


def test_the_gap_no_float_can_measure_is_decided_to_the_last_digit() -> None:
    """Exact, not merely large: the boundary lands where the arithmetic says it does.

    ``abs(0.0 - 10**5000)`` is ``10**5000`` exactly, so a tolerance of ``10**5000``
    holds -- the comparison is inclusive here as everywhere -- and one digit less
    does not. A float somewhere in this path would round both to the same
    infinity and answer the same way twice.
    """
    expect(0.0).is_close_to(10**5000, tol=10**5000)
    expect(0.0).is_close_to(10**5000, rel=1)
    with pytest.raises(AssertionFailure, match="further from it than any float can measure"):
        expect(0.0).is_close_to(10**5000, tol=10**5000 - 1)
    expect(0.0).is_not_close_to(10**5000, tol=10**5000 - 1)
    # A half is a half of the *exact* target, not of a rounded one.
    expect(5 * 10**4999).is_close_to(10**5000, rel=0.5)
    with pytest.raises(AssertionFailure, match="to be within"):
        expect(5 * 10**4999 - 10**4000).is_close_to(10**5000, rel=0.5)


def test_the_exact_gap_respects_signs_and_fractions() -> None:
    """Both halves of the rearranged inequality, each with a case that needs it.

    The gap is a *difference*, so a target on the far side of zero is further
    away and not nearer; and the tolerance is compared against a fraction, so the
    denominator a non-integral operand contributes has to be carried through or
    the band comes out scaled by it. Every other case in this file puts a whole
    number on at least one side, where both mistakes are invisible.
    """
    expect(-1.0).is_close_to(10**5000, tol=10**5000 + 1)
    with pytest.raises(AssertionFailure, match="further from it than any float can measure"):
        expect(-1.0).is_close_to(10**5000, tol=10**5000)
    expect(10**5000).is_close_to(0.5, tol=10**5000)
    with pytest.raises(AssertionFailure, match="further from it than any float can measure"):
        expect(10**5000).is_close_to(0.5, tol=10**5000 - 1)


def test_an_infinite_operand_has_no_exact_gap_to_compute() -> None:
    """An infinity is not a rational number, and the exact path must not ask it for one.

    ``float("inf").as_integer_ratio()`` raises, so reaching the arithmetic with
    an infinity on either side would turn a failing assertion into a library
    error. The answer is the one the measurable path gives: an unequal infinity
    is beyond every finite tolerance, and ``tol=inf`` still covers everything.
    """
    with pytest.raises(AssertionFailure, match="further from it than any float can measure"):
        expect(10**5000).is_close_to(INF, tol=10**5000)
    with pytest.raises(AssertionFailure, match="further from it than any float can measure"):
        expect(-INF).is_close_to(10**5000, tol=10**5000)
    expect(10**5000).is_not_close_to(INF, tol=10**5000)
    expect(10**5000).is_close_to(INF, tol=INF)


# ---------------------------------------------------------------------------
# Decimal and Fraction against a float tolerance
# ---------------------------------------------------------------------------
def test_a_decimal_operand_raises_as_soon_as_arithmetic_is_needed() -> None:
    """``==`` crosses the two number systems; ``-`` and ``*`` refuse to, and are left to.

    Both checkers already reject a ``Decimal`` here -- it is not ``int | float`` --
    so reaching this code means the rejection was ignored. What happens then is
    Python's own answer, unmediated: ``Decimal("1.0") == 1.0`` is exactly true, so
    an assertion that never has to subtract simply holds, while anything that
    measures a distance or scales a relative band by the target's magnitude meets
    the refusal. Coercing instead would mean picking one of two representations
    that deliberately disagree -- ``Decimal("0.1") == 0.1`` is false -- which is
    the one reason to be holding a ``Decimal`` at all. ``_ordered`` draws the
    same line for the comparisons, where ``is_zero`` answers a ``Decimal`` NaN and
    ``is_positive`` signals.
    """
    expect(1.0).is_close_to(as_number(Decimal("1.0")), tol=0.5)
    with pytest.raises(TypeError):
        expect(1.0).is_close_to(as_number(Decimal("2.0")), tol=0.5)
    with pytest.raises(TypeError):
        expect(1.0).is_close_to(as_number(Decimal("1.0")))
    with pytest.raises(TypeError):
        expect(1.0).is_not_close_to(as_number(Decimal("1.0")), rel=1e-3)


def test_a_decimal_subject_asked_for_by_name_meets_the_same_boundary() -> None:
    """The other direction, and the same rule.

    ``expect(Decimal(...))`` does not produce this subject -- it produces an
    ``OrderedExpect``, which has no closeness assertion at all
    (``tests/test_ordered.py``). Asking for this one by name gets a subject whose
    value cannot be subtracted from a float tolerance's world, and the same
    equality exemption.

    The ask itself is a checker error now, which is the better place for it to
    fail: ``as_`` takes a ``Callable[[V], X]``, so a subject whose values are
    ``int | float`` cannot be handed a ``Decimal``. That half is pinned in
    ``typing_tests/negative/numeric_negative.py``; this half is what the runtime
    does when the rejection is ignored, so the value goes through
    :func:`as_number` exactly as it does everywhere else in this file.
    """
    with pytest.raises(TypeError):
        expect(as_number(Decimal("1.5")), as_=NumericExpect).is_close_to(1.0, tol=0.5)
    with pytest.raises(TypeError):
        expect(as_number(Decimal("1.5")), as_=NumericExpect).is_close_to(1.0)
    expect(as_number(Decimal("1.0")), as_=NumericExpect).is_close_to(1.0, tol=0.5)


def test_a_fraction_interoperates_where_a_decimal_does_not() -> None:
    """Recorded because the asymmetry is real and surprises people.

    ``Fraction`` is built to mix with ``float`` and ``Decimal`` is built not to,
    so the same laundered call that raises above simply works here. Still a type
    error -- ``Fraction`` is not ``int | float`` either -- and still not a
    routing this library offers; the runtime answer is pinned so that a future
    change to it is a decision rather than an accident.
    """
    expect(1.0).is_close_to(as_number(Fraction(1, 1)))
    expect(0.5).is_close_to(as_number(Fraction(1, 2)), tol=0.01)
    with pytest.raises(AssertionFailure, match="to be within"):
        expect(1.0).is_close_to(as_number(Fraction(1, 2)))


# ---------------------------------------------------------------------------
# NaN
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "assertion",
    [
        pytest.param(lambda: expect(NAN).is_greater_than(0), id="is_greater_than"),
        pytest.param(lambda: expect(NAN).is_greater_than_or_equal_to(0), id="is_greater_or_equal"),
        pytest.param(lambda: expect(NAN).is_less_than(0), id="is_less_than"),
        pytest.param(lambda: expect(NAN).is_less_than_or_equal_to(0), id="is_less_or_equal"),
        pytest.param(lambda: expect(NAN).is_positive(), id="is_positive"),
        pytest.param(lambda: expect(NAN).is_negative(), id="is_negative"),
        pytest.param(lambda: expect(NAN).is_zero(), id="is_zero"),
        pytest.param(lambda: expect(NAN).is_between(0, 1), id="is_between"),
        pytest.param(lambda: expect(NAN).is_strictly_between(0, 1), id="is_strictly_between"),
        pytest.param(lambda: expect(NAN).is_close_to(0.0, tol=1.0), id="is_close_to"),
        pytest.param(lambda: expect(NAN).is_infinite(), id="is_infinite"),
    ],
)
def test_a_nan_subject_fails_every_positive_claim(assertion: Callable[[], object]) -> None:
    """NaN compares false against everything, so nothing positive can be asserted of it."""
    with pytest.raises(AssertionFailure):
        assertion()


def test_a_nan_subject_passes_the_negations() -> None:
    """The negations stay exact complements; a NaN is outside every claim made above."""
    expect(NAN).is_not_zero()
    expect(NAN).is_not_between(0, 1)
    expect(NAN).is_not_close_to(NAN, tol=1.0)
    expect(NAN).is_not_infinite()
    expect(NAN).is_not_equal_to(NAN)


def test_is_equal_to_cannot_assert_a_nan() -> None:
    """``nan == nan`` is false. ``is_nan`` exists precisely because of that."""
    reading = NAN
    with pytest.raises(AssertionFailure) as caught:
        expect(reading).is_equal_to(NAN)
    assert str(caught.value) == (
        "Expected reading to equal nan, but was nan.\n"
        "  both are nan, and a NaN is equal to nothing, itself included"
    )
    expect(reading).is_nan()


def test_a_nan_is_close_to_nothing_including_itself() -> None:
    """And the message says so, because there is no distance to report."""
    reading = NAN
    with pytest.raises(AssertionFailure) as caught:
        expect(reading).is_close_to(NAN, tol=1.0)
    assert str(caught.value) == (
        "Expected reading to be within 1.0 of nan, but was nan"
        " (a NaN is close to nothing, itself included)."
    )
    measured = 1.0
    with pytest.raises(AssertionFailure) as caught:
        expect(measured).is_close_to(NAN, tol=1.0)
    assert str(caught.value) == (
        "Expected measured to be within 1.0 of nan, but was 1.0"
        " (a NaN is close to nothing, itself included)."
    )


def test_a_nan_target_makes_is_not_close_to_vacuous() -> None:
    """Pinned because it is a trap, not because it is nice.

    A NaN compares unequal to everything, so ``is_not_close_to(nan)`` can never
    fail. That is what ``!= pytest.approx(nan)`` does too, and matching the
    ecosystem beats inventing a third answer -- but a reader who lands here
    should find it written down rather than discover it from a green test.
    """
    expect(1.0).is_not_close_to(NAN, tol=1.0)
    expect(NAN).is_not_close_to(NAN, tol=1.0)


def test_is_nan_reports_the_value() -> None:
    ratio = 1.5
    with pytest.raises(AssertionFailure) as caught:
        expect(ratio).is_nan()
    assert str(caught.value) == "Expected ratio to be NaN, but was 1.5."


def test_is_not_nan_states_that_it_was() -> None:
    reading = NAN
    with pytest.raises(AssertionFailure) as caught:
        expect(reading).is_not_nan()
    assert str(caught.value) == "Expected reading not to be NaN, but it was."


def test_an_int_is_never_a_nan() -> None:
    expect(3).is_not_nan()
    with pytest.raises(AssertionFailure, match="to be NaN"):
        expect(3).is_nan()


# ---------------------------------------------------------------------------
# Infinity
# ---------------------------------------------------------------------------
def test_is_infinite_covers_both_signs() -> None:
    expect(INF).is_infinite()
    expect(-INF).is_infinite()
    expect(1e308).is_not_infinite()


def test_is_infinite_reports_the_value() -> None:
    reading = 1.5
    with pytest.raises(AssertionFailure) as caught:
        expect(reading).is_infinite()
    assert str(caught.value) == "Expected reading to be infinite, but was 1.5."


def test_is_not_infinite_reports_which_infinity_it_found() -> None:
    reading = -INF
    with pytest.raises(AssertionFailure) as caught:
        expect(reading).is_not_infinite()
    assert str(caught.value) == "Expected reading not to be infinite, but was -inf."


def test_infinity_orders_like_a_number() -> None:
    expect(INF).is_greater_than(1e308)
    expect(INF).is_positive()
    expect(-INF).is_negative()
    expect(INF).is_not_between(0, 1)
    with pytest.raises(AssertionFailure, match="to be between"):
        expect(INF).is_between(0, 1)


def test_two_equal_infinities_are_close_to_each_other() -> None:
    """``inf - inf`` is NaN, so equality has to be answered before the subtraction."""
    expect(INF).is_close_to(INF, tol=0.0)
    expect(-INF).is_close_to(-INF, tol=0.0)


def test_an_infinity_is_far_from_everything_else() -> None:
    expect(INF).is_not_close_to(-INF, tol=1e308)
    expect(INF).is_not_close_to(0.0, tol=1e308)


# ---------------------------------------------------------------------------
# Numbers too large to put in a message
# ---------------------------------------------------------------------------
def test_an_unprintable_integer_is_described_rather_than_printed() -> None:
    """A failing assertion must report, not blow up inside its own message.

    CPython refuses to convert an integer of more than
    ``sys.get_int_max_str_digits()`` digits to text at all, so a bare ``repr``
    turns the failure into a ``ValueError`` about string conversion -- an error
    with nothing to do with the assertion, raised from a code path that only runs
    when a test is already red.
    """
    huge = 10**5000
    assert sys.get_int_max_str_digits() < 5000, "the wall this test is about is gone"
    with pytest.raises(AssertionFailure) as caught:
        expect(huge).is_negative()
    assert (
        str(caught.value) == "Expected huge to be negative, but was <integer of about 5001 digits>."
    )


def test_an_unprintable_integer_operand_is_described_too() -> None:
    """The subject is not the only number that reaches a message."""
    count = 1
    with pytest.raises(AssertionFailure) as caught:
        expect(count).is_greater_than(10**5000)
    assert str(caught.value) == (
        "Expected count to be greater than <integer of about 5001 digits>, but was 1."
    )


def test_an_unprintable_negative_integer_keeps_its_sign() -> None:
    """Otherwise ``to be positive, but was <integer of ...>`` would not say which way."""
    huge = -(10**5000)
    with pytest.raises(AssertionFailure) as caught:
        expect(huge).is_positive()
    assert str(caught.value) == (
        "Expected huge to be positive, but was -<integer of about 5001 digits>."
    )


def test_an_unprintable_bound_does_not_break_the_caller_bug_report() -> None:
    """The ``ValueError`` guards render numbers too, and are hit before the subject."""
    with pytest.raises(ValueError, match="inverted") as caught:
        expect(3).is_between(10**5000, 1)
    assert str(caught.value) == (
        "range is inverted: low <integer of about 5001 digits> exceeds high 1"
    )


def test_a_merely_long_integer_is_clipped_not_dumped() -> None:
    """Below the wall the digits exist, but 200 of them is still a wall to read."""
    long_id = 10**200
    with pytest.raises(AssertionFailure) as caught:
        expect(long_id).is_negative()
    message = str(caught.value)
    assert message.startswith("Expected long_id to be negative, but was 1000000")
    assert message.endswith("... (truncated from 201 characters).")
    assert len(message) < 200


def test_an_integer_that_fits_is_left_alone() -> None:
    """The clipping must not touch the numbers real tests actually use."""
    account = 2**64
    with pytest.raises(AssertionFailure) as caught:
        expect(account).is_negative()
    assert str(caught.value) == "Expected account to be negative, but was 18446744073709551616."


def test_a_distance_no_float_can_hold_still_produces_a_verdict() -> None:
    """``10**5000 - 1.0`` raises ``OverflowError``; the assertion still has an answer.

    The subject is astronomically far from the target, which is all
    ``is_close_to`` was asked. Crashing on the subtraction would throw away a
    verdict the comparison had already earned.
    """
    reading = 10**5000
    with pytest.raises(AssertionFailure) as caught:
        expect(reading).is_close_to(1.0, tol=0.5)
    assert str(caught.value) == (
        "Expected reading to be within 0.5 of 1.0, but was <integer of about 5001 digits>"
        ", further from it than any float can measure."
    )
    expect(reading).is_not_close_to(1.0, tol=0.5)


def test_only_an_infinite_tolerance_covers_an_unmeasurable_distance() -> None:
    """The gap is finite -- merely past every float -- so ``inf`` does cover it."""
    reading = 10**5000
    expect(reading).is_close_to(1.0, tol=INF)
    with pytest.raises(AssertionFailure) as caught:
        expect(reading).is_not_close_to(1.0, tol=INF)
    assert str(caught.value) == (
        "Expected reading not to be within inf of 1.0, but was <integer of about 5001 digits>."
    )


# ---------------------------------------------------------------------------
# The rows this catalogue shares with the generic subject
# ---------------------------------------------------------------------------
def test_the_inherited_catalogue_reaches_a_numeric_subject() -> None:
    """``is_equal_to``, ``matches`` and ``is_one_of`` answer for a number too.

    They are inherited rather than reimplemented, which is exactly why they are
    worth a test: nothing else here would notice if the subject stopped being an
    ``Expect``.
    """
    subject = expect(5)
    assert subject.is_equal_to(5) is subject
    assert subject.is_one_of(3, 5, 7) is subject
    assert subject.matches(lambda value: value > 0) is subject
    with pytest.raises(AssertionFailure, match="to be one of"):
        expect(5).is_one_of(1, 2)


# ---------------------------------------------------------------------------
# Which values actually reach this subject
# ---------------------------------------------------------------------------
def test_int_subclasses_reach_the_numeric_subject() -> None:
    class Count(int):
        __slots__ = ()

    assert isinstance(expect(Count(3)), NumericExpect)
    expect(Count(3)).is_positive()


def test_decimal_and_fraction_are_ordered_values_and_not_numeric_subjects() -> None:
    """Checked rather than assumed, because the answer is not the intuitive one.

    ``Decimal`` and ``Fraction`` register with the ``numbers`` ABCs, not with the
    built-ins, so ``issubclass(Decimal, int | float)`` is false and neither is
    this subject's business. They lose no assertion by it: the comparisons, the
    ranges and the sign assertions live one level up, in ``OrderedExpect``, and
    that is the subject they get. ``tests/test_ordered.py`` owns that half.
    """
    assert not issubclass(Decimal, int | float)
    assert not issubclass(Fraction, int | float)
    for value in (Decimal("1.5"), Fraction(1, 2)):
        # Held as `object` deliberately: statically this is already an
        # `Expect[Decimal | Fraction]`, and mypy would call the runtime check
        # unreachable rather than let it run.
        subject: object = expect(value)
        assert not isinstance(subject, NumericExpect)


# ---------------------------------------------------------------------------
# Chaining, the happy path, and `because`
# ---------------------------------------------------------------------------
def test_every_assertion_hands_back_the_same_subject() -> None:
    subject = expect(5)
    assert subject.is_positive().and_.is_between(1, 10).and_.is_not_nan() is subject


def test_passing_numeric_assertions_never_touch_the_failure_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A passing assertion never reaches the failure path, argument checks and all.

    ``tests/test_happy_path.py`` owns the general form of this guard. The ranges
    and tolerances get their own because they do work *before* the comparison,
    which is the obvious place to start building a message by accident.
    """

    def detonate(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("a passing assertion reached the failure path")

    monkeypatch.setattr(Expect, "_fail", detonate)
    expect(5).is_positive().and_.is_between(1, 10).and_.is_strictly_between(1, 10)
    expect(5.0).is_close_to(5.25, tol=0.5).and_.is_not_close_to(9.0, tol=0.5)
    expect(5.0).is_close_to(5.0).and_.is_close_to(5.001, rel=1e-3)
    expect(5.0).is_close_to(5.001, tol=0.1, rel=1e-9).and_.is_not_close_to(9.0, rel=1e-3)
    expect(5.0).is_not_nan().and_.is_not_infinite().and_.is_not_zero()


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda: expect(1).is_greater_than(2, because="R"), id="is_greater_than"),
        pytest.param(
            lambda: expect(1).is_greater_than_or_equal_to(2, because="R"), id="is_greater_or_equal"
        ),
        pytest.param(lambda: expect(2).is_less_than(1, because="R"), id="is_less_than"),
        pytest.param(
            lambda: expect(2).is_less_than_or_equal_to(1, because="R"), id="is_less_or_equal"
        ),
        pytest.param(lambda: expect(-1).is_positive(because="R"), id="is_positive"),
        pytest.param(lambda: expect(1).is_negative(because="R"), id="is_negative"),
        pytest.param(lambda: expect(1).is_zero(because="R"), id="is_zero"),
        pytest.param(lambda: expect(0).is_not_zero(because="R"), id="is_not_zero"),
        pytest.param(lambda: expect(9).is_between(1, 5, because="R"), id="is_between"),
        pytest.param(lambda: expect(3).is_not_between(1, 5, because="R"), id="is_not_between"),
        pytest.param(
            lambda: expect(5).is_strictly_between(1, 5, because="R"), id="is_strictly_between"
        ),
        pytest.param(lambda: expect(9.0).is_close_to(1.0, tol=0.5, because="R"), id="is_close_to"),
        pytest.param(
            lambda: expect(1.0).is_not_close_to(1.0, tol=0.5, because="R"), id="is_not_close_to"
        ),
        pytest.param(lambda: expect(9.0).is_close_to(1.0, because="R"), id="is_close_to_default"),
        pytest.param(
            lambda: expect(9.0).is_close_to(1.0, rel=1e-3, because="R"), id="is_close_to_rel"
        ),
        pytest.param(
            lambda: expect(9.0).is_close_to(1.0, tol=0.5, rel=1e-3, because="R"),
            id="is_close_to_both",
        ),
        pytest.param(
            lambda: expect(1.0).is_not_close_to(1.0, rel=1e-3, because="R"),
            id="is_not_close_to_rel",
        ),
        pytest.param(lambda: expect(1.0).is_nan(because="R"), id="is_nan"),
        pytest.param(lambda: expect(NAN).is_not_nan(because="R"), id="is_not_nan"),
        pytest.param(lambda: expect(1.0).is_infinite(because="R"), id="is_infinite"),
        pytest.param(lambda: expect(INF).is_not_infinite(because="R"), id="is_not_infinite"),
    ],
)
def test_because_reaches_every_assertion(call: Callable[[], object]) -> None:
    with pytest.raises(AssertionFailure, match="because R"):
        call()
