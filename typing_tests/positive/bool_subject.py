"""``BoolExpect``: dispatch, and what every call in a boolean chain is worth.

This file is also the static half of an ordering contract. ``bool`` is a subclass
of ``int``, so its overload has to sit *above* ``int | float`` in ``expect()``;
the day it slips below, ``expect(flag)`` answers with a ``NumericExpect`` and the
whole catalogue below silently disappears from the subject.
``typing_tests/negative/bool_negative.py`` is the other half: it pins the same
fact from the failing side, and pins the ways the subject could get *looser*
without a single line here changing colour.
"""

from typing import Self, assert_type

from lovely_assertions import (
    BoolExpect,
    Expect,
    Found,
    custom_assertion,
    expect,
)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
def bool_wins_over_the_int_it_subclasses(flag: bool) -> None:
    assert_type(expect(True), BoolExpect)
    assert_type(expect(False), BoolExpect)
    assert_type(expect(flag), BoolExpect)


def subject_comes_back_as_a_bool(flag: bool) -> None:
    """Not ``int``: the subject keeps the type it was wrapped with."""
    assert_type(expect(flag).subject, bool)
    assert_type(expect(flag).and_, BoolExpect)


# ---------------------------------------------------------------------------
# The catalogue returns the subject, every time
# ---------------------------------------------------------------------------
def every_assertion_hands_the_subject_back(flag: bool) -> None:
    assert_type(expect(flag).is_true(), BoolExpect)
    assert_type(expect(flag).is_false(), BoolExpect)
    assert_type(expect(flag).is_not_true(), BoolExpect)
    assert_type(expect(flag).is_not_false(), BoolExpect)
    assert_type(expect(flag).implies(True), BoolExpect)


def because_is_accepted_and_changes_nothing(flag: bool) -> None:
    assert_type(expect(flag).is_true(because="the feature is on"), BoolExpect)
    assert_type(expect(flag).is_not_false(because="R"), BoolExpect)
    assert_type(expect(flag).implies(True, because="an admin can always read"), BoolExpect)


def the_inherited_catalogue_is_bound_to_bool(flag: bool) -> None:
    """``Expect[T]`` must see ``T = bool`` here, not the ``int`` a bool subclasses.

    The generic members are where a wrong base parameter hides: ``matches`` would
    hand the predicate an ``int``, and nothing in the boolean catalogue proper
    would notice.
    """
    assert_type(expect(flag).matches(lambda value: value is True), BoolExpect)
    assert_type(expect(flag).satisfies(lambda value: expect(value).is_true()), BoolExpect)
    assert_type(expect(flag).is_not_equal_to(False), BoolExpect)


def chaining_survives_the_inherited_catalogue(flag: bool) -> None:
    """A chain that mixes ``Expect[T]``'s assertions in must stay a ``BoolExpect``."""
    assert_type(expect(flag).is_true().and_, BoolExpect)
    assert_type(expect(flag).is_true().and_.is_equal_to(True), BoolExpect)
    assert_type(expect(flag).is_equal_to(True).and_.implies(False), BoolExpect)
    assert_type(expect(flag).is_one_of(True, False).and_.is_not_true(), BoolExpect)
    assert_type(expect(flag).is_true().and_.is_false().and_.implies(True).subject, bool)


# ---------------------------------------------------------------------------
# Narrowing assertions inherited from Expect[T]
# ---------------------------------------------------------------------------
def narrowing_widens_rather_than_relabels(flag: bool) -> None:
    """``is_not_none`` returns ``Expect[bool]``: it widens rather than re-specialises.

    A narrowing assertion cannot name the subject it was called on -- the object
    may be a ``BoolExpect`` subclass that no re-specialisation would describe --
    so it answers with the supertype that is sound for all of them.
    """
    assert_type(expect(flag).is_not_none(), Expect[bool])
    assert_type(expect(flag).is_not_none().subject, bool)


def is_instance_of_finds_the_int_underneath(flag: bool) -> None:
    """A ``bool`` really is an ``int``; ``.which`` is where that becomes usable."""
    found = expect(flag).is_instance_of(int)
    assert_type(found, Found[BoolExpect, int])
    assert_type(found.and_, BoolExpect)
    assert_type(found.and_.is_true(), BoolExpect)
    assert_type(found.which, Expect[int])
    assert_type(found.subject, int)


# ---------------------------------------------------------------------------
# Extension subjects
# ---------------------------------------------------------------------------
class FeatureFlagExpect(BoolExpect):
    """A domain subject built on ``BoolExpect`` rather than on ``Expect[T]``."""

    __slots__ = ()

    @custom_assertion
    def is_enabled(self, *, because: str = "") -> Self:
        if self._subject:
            return self
        return self._fail("to be enabled, but the flag was off", because)


def a_subclass_keeps_its_own_type_through_the_bool_catalogue(flag: bool) -> None:
    subject = FeatureFlagExpect(flag)
    assert_type(subject.is_true(), FeatureFlagExpect)
    assert_type(subject.implies(True), FeatureFlagExpect)
    assert_type(subject.is_true().and_.is_enabled(), FeatureFlagExpect)
    assert_type(subject.is_enabled().and_.is_not_false().subject, bool)
