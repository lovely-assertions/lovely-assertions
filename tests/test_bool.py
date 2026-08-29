"""Booleans -- ``BoolExpect``.

Two halves. The four value assertions, which are strict about ``True`` and
``False`` rather than merely truthy, and ``implies``, whose failure message has
to carry the truth table for whoever reads it at 2am.
"""

from collections.abc import Callable
from typing import cast

import pytest

from lovely_assertions import AssertionFailure, BoolExpect, expect, soft_assertions


def test_expect_dispatches_a_bool_to_the_bool_subject() -> None:
    """``bool`` is an ``int``; everything below exists only if dispatch says so."""
    assert isinstance(expect(True), BoolExpect)
    assert isinstance(expect(False), BoolExpect)


@pytest.mark.usefixtures("no_failure_machinery")
def test_a_passing_assertion_never_touches_the_failure_path() -> None:
    """A passing assertion never reaches the failure machinery at all.

    ``conftest``'s trap arms every module the package has, and
    ``tests/test_happy_path.py`` runs the same trap over the generic subject. It
    is worth re-arming here because most of the calls below take a branch that no
    other file exercises.
    """
    expect(True).is_true(because="the reason must not be read either")
    expect(False).is_false()
    expect(False).is_not_true()
    expect(True).is_not_false()
    expect(False).implies(False)
    expect(True).implies(True)


# ---------------------------------------------------------------------------
# is_true / is_false
# ---------------------------------------------------------------------------
def test_is_true_passes_and_chains() -> None:
    subject = expect(True)
    assert subject.is_true() is subject


def test_is_true_reports_the_actual_value() -> None:
    enabled = False
    with pytest.raises(AssertionFailure) as caught:
        expect(enabled).is_true()
    assert str(caught.value) == "Expected enabled to be True, but was False."


def test_is_false_passes_and_chains() -> None:
    subject = expect(False)
    assert subject.is_false() is subject


def test_is_false_reports_the_actual_value() -> None:
    enabled = True
    with pytest.raises(AssertionFailure) as caught:
        expect(enabled).is_false()
    assert str(caught.value) == "Expected enabled to be False, but was True."


# ---------------------------------------------------------------------------
# The negated pair (FluentAssertions parity)
# ---------------------------------------------------------------------------
def test_is_not_true_accepts_false() -> None:
    subject = expect(False)
    assert subject.is_not_true() is subject


def test_is_not_true_states_that_it_was() -> None:
    enabled = True
    with pytest.raises(AssertionFailure) as caught:
        expect(enabled).is_not_true()
    assert str(caught.value) == "Expected enabled not to be True, but it was."


def test_is_not_false_accepts_true() -> None:
    subject = expect(True)
    assert subject.is_not_false() is subject


def test_is_not_false_states_that_it_was() -> None:
    enabled = False
    with pytest.raises(AssertionFailure) as caught:
        expect(enabled).is_not_false()
    assert str(caught.value) == "Expected enabled not to be False, but it was."


def test_the_negated_pair_says_something_different_from_the_positive_one() -> None:
    """The two names exist to read differently; the messages must too."""
    with pytest.raises(AssertionFailure) as positive:
        expect(True).is_false()
    with pytest.raises(AssertionFailure) as negated:
        expect(True).is_not_true()
    assert str(positive.value) != str(negated.value)


# ---------------------------------------------------------------------------
# Strictness
# ---------------------------------------------------------------------------
def test_the_value_checks_are_identity_not_truthiness() -> None:
    """``is_true`` asks for ``True``, not for something that happens to be truthy.

    Dispatch only ever routes an exact ``bool`` to this subject, so a hand-built
    one is the only way to observe the difference -- which is exactly the case
    the strictness is for: a ``1`` or a NumPy scalar that reached a boolean
    assertion is a finding, not a pass.

    All four are pinned, not just the positive pair: under a truthiness reading
    ``is_not_true`` would reject a ``1`` and ``is_not_false`` would accept a
    ``0``, so the two negated names are where the difference shows up as a
    *passing* assertion -- the direction nobody notices.
    """
    truthy = BoolExpect(cast("bool", 1))
    with pytest.raises(AssertionFailure, match="to be True, but was 1"):
        truthy.is_true()
    with pytest.raises(AssertionFailure, match="to be False, but was 1"):
        truthy.is_false()
    assert truthy.is_not_true() is truthy
    assert truthy.is_not_false() is truthy

    falsy = BoolExpect(cast("bool", 0))
    with pytest.raises(AssertionFailure, match="to be False, but was 0"):
        falsy.is_false()
    assert falsy.is_not_false() is falsy


# ---------------------------------------------------------------------------
# implies
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("subject", "consequent"),
    [(False, False), (False, True), (True, True)],
)
def test_implies_holds_for_three_of_the_four_rows(subject: bool, consequent: bool) -> None:
    wrapper = expect(subject)
    assert wrapper.implies(consequent) is wrapper


def test_implies_fails_only_when_the_subject_holds_and_the_consequent_does_not() -> None:
    is_admin = True
    with pytest.raises(AssertionFailure) as caught:
        expect(is_admin).implies(False)
    assert str(caught.value) == (
        "Expected is_admin to imply the consequent, but was True while the consequent was False."
    )


def test_implies_reports_the_subject_it_actually_saw() -> None:
    """The failing row is "the subject held" -- the message must say *what* held.

    ``implies`` reads the subject for truth rather than for identity, so it is
    the one method here a non-``bool`` can reach and still be judged. A message
    that answered ``True`` regardless would turn the interesting case -- a
    ``"yes"`` that got as far as a boolean assertion -- into a plausible lie.
    """
    truthy = BoolExpect(cast("bool", "yes"))
    with pytest.raises(AssertionFailure) as caught:
        truthy.implies(False)
    assert "but was 'yes' while the consequent was False" in str(caught.value)


def test_implies_reports_a_non_bool_consequent_as_it_was_given() -> None:
    """The other half of the same honesty: ``!r``, not a re-spelt ``False``."""
    with pytest.raises(AssertionFailure, match="the consequent was 0"):
        expect(True).implies(cast("bool", 0))


def test_implies_names_both_sides_so_the_reader_need_not_recall_the_truth_table() -> None:
    """The one failing row is the one people get wrong; say which side gave way."""
    with pytest.raises(AssertionFailure) as caught:
        expect(True).implies(False)
    message = str(caught.value)
    assert "was True" in message
    assert "the consequent was False" in message


# ---------------------------------------------------------------------------
# Chaining, inheritance, soft scopes
# ---------------------------------------------------------------------------
def test_the_catalogue_chains_with_the_inherited_one() -> None:
    enabled = True
    assert expect(enabled).is_true().and_.is_equal_to(True).and_.implies(True).subject is True


def test_every_broken_clause_is_reported_in_a_soft_scope() -> None:
    """``_fail`` hands the subject back, so a soft block reports the whole chain."""
    enabled = True
    with pytest.raises(AssertionFailure) as caught, soft_assertions():
        expect(enabled).is_false().and_.is_not_true().and_.implies(False)
    message = str(caught.value)
    assert "3 assertions failed:" in message
    assert "Expected enabled to be False, but was True" in message
    assert "Expected enabled not to be True, but it was" in message
    assert (
        "Expected enabled to imply the consequent, but was True "
        "while the consequent was False" in message
    )


# ---------------------------------------------------------------------------
# because reaches all of them
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda: expect(False).is_true(because="R"), id="is_true"),
        pytest.param(lambda: expect(True).is_false(because="R"), id="is_false"),
        pytest.param(lambda: expect(True).is_not_true(because="R"), id="is_not_true"),
        pytest.param(lambda: expect(False).is_not_false(because="R"), id="is_not_false"),
        pytest.param(lambda: expect(True).implies(False, because="R"), id="implies"),
    ],
)
def test_because_reaches_every_assertion(call: Callable[[], object]) -> None:
    with pytest.raises(AssertionFailure, match="because R"):
        call()
