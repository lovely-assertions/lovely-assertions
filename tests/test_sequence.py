"""The sequence catalogue: ``SequenceExpect[E]``, the ordered half.

Two things are being tested here, and the second is the interesting one.

*Behaviour* -- what passes and what fails, including the edges that are easy to
get wrong: an empty sequence is sorted, a list equals the tuple with the same
contents, a predicate set has to be matched one-to-one.

*Messages* -- a collection assertion that only reports "false" leaves the reader
to diff two lists by eye. So the failures are asserted verbatim: the first index
that differs, the items that were extra, the index a nested finding came from.

Half of this catalogue is declared one class up, on ``CollectionExpect[E]``:
everything an unordered collection can answer for itself. Those assertions are
exercised here too, verbatim, and that is the point -- a sequence has positions,
so ``does_not_contain`` says *at index 1* and a nested finding says which index
it came from. If the split ever costs a position, these strings say so. The
order-free readings of the same assertions, and the ``because`` coverage for the
methods ``CollectionExpect`` declares, live in ``tests/test_collection.py``.
"""

import inspect
from typing import TYPE_CHECKING, Final, cast

import pytest

from _happy_calls import declared_by_the_subject
from lovely_assertions import AssertionFailure, Found, SequenceExpect, expect
from lovely_assertions._sequence import _pairs

if TYPE_CHECKING:
    from collections.abc import Sequence


class Animal:
    __slots__ = ()

    def __repr__(self) -> str:
        return "Animal()"


class Dog(Animal):
    __slots__ = ()

    def __repr__(self) -> str:
        return "Dog()"


class Row:
    """A record with fields worth extracting -- the subject ``key=`` and ``extracting`` serve.

    Distinct objects carrying the same id, which is the point: uniqueness *of the
    row* reports nothing, and uniqueness of ``row.id`` is the question being asked.
    """

    __slots__ = ("email", "id")

    def __init__(self, identifier: int, email: str | None, /) -> None:
        self.id = identifier
        self.email = email

    def __repr__(self) -> str:
        return "Row(" + str(self.id) + ")"


def row_id(row: Row, /) -> int:
    """A named key, so a failure message can be asserted against its name."""
    return row.id


def email_of(row: Row, /) -> str | None:
    """A named key whose result is allowed to be missing."""
    return row.email


def is_even(value: int) -> bool:
    """A named predicate, so the message can be asserted against its name."""
    return value % 2 == 0


#: An empty sequence with a known element type. A bare ``[]`` leaves the element
#: type unsolved, which is exactly what the strict typing surface should reject.
EMPTY: list[int] = []


def negated(value: int) -> int:
    """A named sort key for the sweep of passing calls; a lambda would do as well."""
    return -value


def missing_sequence() -> SequenceExpect[int]:
    """A subject whose value is ``None`` -- a cast is how one really gets here."""
    return SequenceExpect[int](cast("Sequence[int]", None))


# ---------------------------------------------------------------------------
# Emptiness
# ---------------------------------------------------------------------------
def test_is_empty_passes_and_chains() -> None:
    subject = expect(EMPTY)
    assert subject.is_empty() is subject


def test_is_empty_shows_the_collection() -> None:
    items = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).is_empty()
    assert str(caught.value) == "Expected items to be empty, but was [1, 2, 3]."


def test_is_not_empty() -> None:
    expect([1]).is_not_empty()
    items: list[int] = []
    with pytest.raises(AssertionFailure) as caught:
        expect(items).is_not_empty()
    assert str(caught.value) == "Expected items not to be empty, but it was."


def test_is_none_or_empty_accepts_both_cases() -> None:
    expect(EMPTY).is_none_or_empty()
    subject = missing_sequence()
    assert subject.is_none_or_empty() is subject


def test_is_none_or_empty_rejects_a_populated_sequence() -> None:
    items = [1]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).is_none_or_empty()
    assert str(caught.value) == "Expected items to be None or empty, but was [1]."


def test_is_not_none_or_empty_reports_which_case_it_was() -> None:
    """The subject is built inside the statement, so the name falls back cleanly."""
    expect([1]).is_not_none_or_empty()
    with pytest.raises(AssertionFailure) as caught:
        missing_sequence().is_not_none_or_empty()
    assert str(caught.value) == "Expected the value not to be None or empty, but was None."

    items: list[int] = []
    with pytest.raises(AssertionFailure) as caught:
        expect(items).is_not_none_or_empty()
    assert str(caught.value) == "Expected items not to be None or empty, but was []."


# ---------------------------------------------------------------------------
# Length
# ---------------------------------------------------------------------------
def test_has_length_reports_both_counts_and_the_collection() -> None:
    expect([1, 2]).has_length(2)
    items = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).has_length(5)
    assert str(caught.value) == "Expected items to have length 5, but had 3: [1, 2, 3]."


def test_does_not_have_length() -> None:
    expect([1, 2]).does_not_have_length(3)
    items = [1, 2]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).does_not_have_length(2)
    assert str(caught.value) == "Expected items not to have length 2, but was [1, 2]."


def test_has_length_matching_names_the_predicate() -> None:
    def is_even(count: int) -> bool:
        return count % 2 == 0

    expect([1, 2]).has_length_matching(is_even)
    items = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).has_length_matching(is_even)
    assert str(caught.value) == (
        "Expected items to have a length matching is_even, but had 3: [1, 2, 3]."
    )


def test_length_comparisons_pass_on_their_boundaries() -> None:
    expect([1, 2]).has_length_greater_than(1)
    expect([1, 2]).has_length_greater_than_or_equal_to(2)
    expect([1, 2]).has_length_less_than(3)
    expect([1, 2]).has_length_less_than_or_equal_to(2)


def test_length_comparisons_say_which_way_they_failed() -> None:
    items = [1, 2]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).has_length_greater_than(3)
    assert str(caught.value) == "Expected items to have more than 3 items, but had 2: [1, 2]."

    with pytest.raises(AssertionFailure) as caught:
        expect(items).has_length_greater_than_or_equal_to(3)
    assert str(caught.value) == "Expected items to have at least 3 items, but had 2: [1, 2]."

    with pytest.raises(AssertionFailure) as caught:
        expect(items).has_length_less_than(2)
    assert str(caught.value) == "Expected items to have fewer than 2 items, but had 2: [1, 2]."

    with pytest.raises(AssertionFailure) as caught:
        expect(items).has_length_less_than_or_equal_to(1)
    assert str(caught.value) == "Expected items to have at most 1 item, but had 2: [1, 2]."


def test_has_same_length_as_accepts_any_collection() -> None:
    expect([1, 2]).has_same_length_as({"a", "b"})
    expect([1, 2]).has_same_length_as({"a": 1, "b": 2})
    items = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).has_same_length_as((1, 2))
    assert str(caught.value) == (
        "Expected items to have the same length as (1, 2), but had 3 items against 2."
    )


def test_does_not_have_same_length_as() -> None:
    expect([1, 2]).does_not_have_same_length_as([1])
    items = [1, 2]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).does_not_have_same_length_as([3, 4])
    assert str(caught.value) == (
        "Expected items not to have the same length as [3, 4], but both had 2 items."
    )


# ---------------------------------------------------------------------------
# Sortable equality
# ---------------------------------------------------------------------------
def test_equals_sequence_compares_items_not_collections() -> None:
    """A list equals the tuple with the same contents: the subject is a Sequence."""
    expect([1, 2, 3]).equals_sequence((1, 2, 3))
    expect(EMPTY).equals_sequence(EMPTY)


def test_equals_sequence_reports_the_first_index_that_differs() -> None:
    items = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).equals_sequence([1, 9, 3])
    assert str(caught.value) == (
        "Expected items to equal [1, 9, 3], but differed at index 1 (2 instead of 9)."
    )


def test_equals_sequence_reports_a_pure_length_mismatch() -> None:
    items = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).equals_sequence([1, 2])
    assert str(caught.value) == "Expected items to equal [1, 2], but had 3 items, not 2."


def test_equals_sequence_reports_both_when_both_are_wrong() -> None:
    items = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).equals_sequence([1, 9])
    assert str(caught.value) == (
        "Expected items to equal [1, 9], but differed at index 1 (2 instead of 9), "
        "and had 3 items, not 2."
    )


def test_does_not_equal_sequence() -> None:
    expect([1, 2]).does_not_equal_sequence([2, 1])
    expect([1, 2]).does_not_equal_sequence([1, 2, 3])
    items = [1, 2]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).does_not_equal_sequence((1, 2))
    assert str(caught.value) == "Expected items not to equal (1, 2), but it did."


def test_equals_approximately_tolerates_drift() -> None:
    expect([1.0, 2.0]).equals_approximately([1.05, 1.98], tol=0.1)
    expect([1, 2]).equals_approximately([1.0, 2.0], tol=0.0)


def test_equals_approximately_reports_the_first_index_beyond_tolerance() -> None:
    readings = [1.0, 2.0]
    with pytest.raises(AssertionFailure) as caught:
        expect(readings).equals_approximately([1.0, 2.5], tol=0.1)
    assert str(caught.value) == (
        "Expected readings to equal [1.0, 2.5] within 0.1, "
        "but differed at index 1 (2.0 instead of 2.5)."
    )


def test_equals_approximately_reports_a_length_mismatch() -> None:
    readings = [1.0]
    with pytest.raises(AssertionFailure) as caught:
        expect(readings).equals_approximately([1.0, 2.0], tol=0.1)
    assert str(caught.value) == (
        "Expected readings to equal [1.0, 2.0] within 0.1, but had 1 item, not 2."
    )


def test_equals_approximately_reports_the_index_and_the_length_together() -> None:
    readings = [1.0, 2.0, 3.0]
    with pytest.raises(AssertionFailure) as caught:
        expect(readings).equals_approximately([1.0, 2.5], tol=0.1)
    assert str(caught.value) == (
        "Expected readings to equal [1.0, 2.5] within 0.1, "
        "but differed at index 1 (2.0 instead of 2.5), and had 3 items, not 2."
    )


def test_equals_approximately_is_inclusive_and_equal_items_always_match() -> None:
    """The contract `NumericExpect.is_close_to` states, item by item.

    Equality is tested before the distance, which is what makes two infinities
    match: `inf - inf` is a NaN, not a distance of zero.
    """
    expect([1.0]).equals_approximately([1.5], tol=0.5)
    expect([float("inf"), 1.0]).equals_approximately([float("inf"), 1.0], tol=0.0)


def test_equals_approximately_never_matches_a_nan() -> None:
    """A NaN is close to nothing, itself included -- and the message says so.

    Written as `not (distance <= tol)` rather than `distance > tol` on purpose:
    every comparison against a NaN is false, so the plain spelling reports no
    difference at all and the assertion passes on any subject.
    """
    nan = float("nan")
    readings = [nan]
    with pytest.raises(AssertionFailure) as caught:
        expect(readings).equals_approximately([1.0], tol=1000.0)
    assert str(caught.value) == (
        "Expected readings to equal [1.0] within 1000.0, but differed at index 0 "
        "(nan instead of 1.0) (a NaN is close to nothing, itself included)."
    )
    with pytest.raises(AssertionFailure, match="a NaN is close to nothing"):
        expect(readings).equals_approximately([nan], tol=1000.0)
    with pytest.raises(AssertionFailure, match="a NaN is close to nothing"):
        expect([1.0]).equals_approximately([nan], tol=1000.0)


def test_equals_approximately_rejects_a_tolerance_nothing_could_be_judged_by() -> None:
    """A test that cannot fail is worse than one that fails loudly."""
    with pytest.raises(ValueError, match="must not be NaN"):
        expect([1.0]).equals_approximately([1.0], tol=float("nan"))
    with pytest.raises(ValueError, match=r"must not be negative, got -0\.5"):
        expect([1.0]).equals_approximately([1.0], tol=-0.5)


def test_starts_with_sequence() -> None:
    expect([1, 2, 3]).starts_with_sequence([1, 2])
    expect([1, 2, 3]).starts_with_sequence([1, 2, 3])
    items = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).starts_with_sequence([1, 9])
    assert str(caught.value) == (
        "Expected items to start with [1, 9], but differed at index 1 (2 instead of 9)."
    )


def test_starts_with_sequence_rejects_a_prefix_that_is_too_long() -> None:
    items = [1, 2]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).starts_with_sequence([1, 2, 3])
    assert str(caught.value) == (
        "Expected items to start with [1, 2, 3], but only had 2 items: [1, 2]."
    )


def test_ends_with_sequence() -> None:
    expect([1, 2, 3]).ends_with_sequence([2, 3])
    expect([1, 2, 3]).ends_with_sequence([1, 2, 3])
    items = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).ends_with_sequence([9, 3])
    assert str(caught.value) == (
        "Expected items to end with [9, 3], but differed at index 1 (2 instead of 9)."
    )


def test_ends_with_sequence_rejects_a_suffix_that_is_too_long() -> None:
    items = [2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).ends_with_sequence([1, 2, 3])
    assert str(caught.value) == (
        "Expected items to end with [1, 2, 3], but only had 2 items: [2, 3]."
    )


# ---------------------------------------------------------------------------
# Element access (the `Found` continuations)
# ---------------------------------------------------------------------------
def test_has_element_at_continues_on_the_element() -> None:
    items = ["a", "b"]
    found = expect(items).has_element_at(1, "b")
    assert isinstance(found, Found)
    assert found.subject == "b"
    assert found.which.is_equal_to("b").subject == "b"
    assert found.and_.has_length(2).subject == items


def test_has_element_at_accepts_a_negative_index() -> None:
    assert expect([1, 2, 3]).has_element_at(-1, 3).subject == 3


def test_has_element_at_accepts_both_ends_of_the_valid_range() -> None:
    """The two indices the bounds check is *inclusive* of, ``-len`` included.

    ``test_has_element_at_rejects_the_indices_just_off_each_end`` pins the pair
    just outside the range; this pins the pair just inside it. Without ``-len``,
    the most-negative index that is really there, narrowing ``-count <= index``
    to ``-count < index`` refuses the first element of every sequence addressed
    from the end and no other test in the suite notices.

    A boundary needs a value on each side of it.
    """
    items = [10, 20, 30]
    assert expect(items).has_element_at(-3, 10).subject == 10
    assert expect(items).has_element_at(0, 10).subject == 10
    assert expect(items).has_element_at(2, 30).subject == 30
    assert expect(items).has_element_at(-1, 30).subject == 30

    one = [7]
    assert expect(one).has_element_at(-1, 7).subject == 7
    assert expect(one).has_element_at(0, 7).subject == 7


def test_has_element_at_reports_the_wrong_value() -> None:
    items = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).has_element_at(1, 9)
    assert str(caught.value) == "Expected items to have 9 at index 1, but had 2: [1, 2, 3]."


def test_has_element_at_reports_an_index_that_is_not_there() -> None:
    items = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).has_element_at(7, 9)
    assert str(caught.value) == (
        "Expected items to have an item at index 7, but only had 3: [1, 2, 3]."
    )


def test_has_element_at_rejects_the_indices_just_off_each_end() -> None:
    """The bounds check is what keeps this an assertion and not an ``IndexError``.

    ``index == len`` and ``index == -len - 1`` are the two that a check off by one
    lets through, and letting either through does not produce a wrong message: it
    produces an ``IndexError`` from inside the library, which is the one outcome
    an assertion must never have. A well-clear index like 7 cannot catch that.
    """
    items = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).has_element_at(3, 9)
    assert str(caught.value) == (
        "Expected items to have an item at index 3, but only had 3: [1, 2, 3]."
    )

    with pytest.raises(AssertionFailure) as caught:
        expect(items).has_element_at(-4, 9)
    assert str(caught.value) == (
        "Expected items to have an item at index -4, but only had 3: [1, 2, 3]."
    )

    empty: list[int] = []
    with pytest.raises(AssertionFailure) as caught:
        expect(empty).has_element_at(0, 9)
    assert str(caught.value) == "Expected empty to have an item at index 0, but only had 0: []."


def test_contains_single_continues_on_the_only_item() -> None:
    found = expect([42]).contains_single()
    assert found.subject == 42
    assert found.which.is_equal_to(42).subject == 42


def test_contains_single_reports_the_count() -> None:
    items = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).contains_single()
    assert str(caught.value) == "Expected items to contain a single item, but had 3: [1, 2, 3]."

    empty: list[int] = []
    with pytest.raises(AssertionFailure) as caught:
        expect(empty).contains_single()
    assert str(caught.value) == "Expected empty to contain a single item, but had 0: []."


# ---------------------------------------------------------------------------
# Set-like relations
# ---------------------------------------------------------------------------
def test_is_subset_of_lists_the_items_that_were_extra() -> None:
    expect([1, 2]).is_subset_of([1, 2, 3])
    expect(EMPTY).is_subset_of([1])
    items = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).is_subset_of({1})
    assert str(caught.value) == "Expected items to be a subset of {1}, but also had [2, 3]."


def test_is_not_subset_of() -> None:
    expect([1, 9]).is_not_subset_of([1, 2])
    items = [1, 2]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).is_not_subset_of([1, 2, 3])
    assert str(caught.value) == (
        "Expected items not to be a subset of [1, 2, 3], but every item was in it."
    )


def test_is_not_subset_of_says_why_an_empty_sequence_fails_it() -> None:
    """An empty collection told that every item was in it reads like a library bug.

    The noun is "collection", not "sequence": the assertion is declared on
    ``CollectionExpect`` and the same sentence has to be true of a set.
    """
    empty: list[int] = []
    with pytest.raises(AssertionFailure) as caught:
        expect(empty).is_not_subset_of([1])
    assert str(caught.value) == (
        "Expected empty not to be a subset of [1], but it had no items "
        "-- an empty collection is a subset of anything."
    )


def test_intersects_and_does_not_intersect() -> None:
    expect([1, 2]).intersects([2, 3])
    expect([1, 2]).does_not_intersect([3, 4])
    items = [1, 2]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).intersects([8, 9])
    assert str(caught.value) == (
        "Expected items to intersect [8, 9], but shared nothing with [1, 2]."
    )
    with pytest.raises(AssertionFailure) as caught:
        expect(items).does_not_intersect([2, 1])
    assert str(caught.value) == "Expected items not to intersect [2, 1], but shared [1, 2]."


# ---------------------------------------------------------------------------
# Containment
# ---------------------------------------------------------------------------
def test_contains_shows_what_was_missing_and_the_collection() -> None:
    expect([1, 2]).contains(2)
    items = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).contains(9)
    assert str(caught.value) == "Expected items to contain 9, but was [1, 2, 3]."


def test_does_not_contain_points_at_the_offending_index() -> None:
    expect([1, 2]).does_not_contain(9)
    items = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).does_not_contain(2)
    assert str(caught.value) == (
        "Expected items not to contain 2, but found it at index 1: [1, 2, 3]."
    )


def test_only_contains_lists_every_item_that_failed() -> None:
    def is_even(value: int) -> bool:
        return value % 2 == 0

    expect([2, 4]).only_contains(is_even)
    items = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).only_contains(is_even)
    assert str(caught.value) == (
        "Expected items to contain only items matching is_even, but [1, 3] did not."
    )


def test_contains_in_order_allows_gaps() -> None:
    expect([1, 9, 2, 9, 3]).contains_in_order(1, 2, 3)
    # A call with no items would assert nothing at all;
    # tests/test_empty_arguments.py pins that as a caller bug.


def test_contains_in_order_reports_a_missing_first_item() -> None:
    items = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).contains_in_order(9, 1)
    assert str(caught.value) == (
        "Expected items to contain (9, 1) in order, but 9 was missing from [1, 2, 3]."
    )


def test_contains_in_order_reports_an_item_that_came_too_early() -> None:
    items = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).contains_in_order(3, 1)
    assert str(caught.value) == (
        "Expected items to contain (3, 1) in order, but 1 did not appear after 3: [1, 2, 3]."
    )


def test_contains_in_order_will_not_let_one_item_serve_twice() -> None:
    """In order means distinct positions, so ``(2, 2)`` needs two twos.

    The scan advances past each item it claims. Without that step the same
    position satisfies both halves of ``contains_in_order(2, 2)`` and the
    assertion passes on a sequence holding a single 2 -- a test that cannot fail,
    one line away in the helper that does the scanning.
    """
    expect([1, 2, 2, 3]).contains_in_order(2, 2)

    items = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).contains_in_order(2, 2)
    assert str(caught.value) == (
        "Expected items to contain (2, 2) in order, but 2 did not appear after 2: [1, 2, 3]."
    )

    expect([1, 2, 3]).does_not_contain_in_order(2, 2)


def test_does_not_contain_in_order() -> None:
    expect([1, 2, 3]).does_not_contain_in_order(3, 1)
    items = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).does_not_contain_in_order(1, 3)
    assert str(caught.value) == (
        "Expected items not to contain (1, 3) in order, but it did: [1, 2, 3]."
    )


def test_contains_in_consecutive_order_requires_adjacency() -> None:
    expect([9, 1, 2, 9]).contains_in_consecutive_order(1, 2)
    items = [1, 9, 2]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).contains_in_consecutive_order(1, 2)
    assert str(caught.value) == (
        "Expected items to contain (1, 2) in consecutive order, "
        "but other items came between them: [1, 9, 2]."
    )


def test_contains_in_consecutive_order_reports_a_missing_item() -> None:
    items = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).contains_in_consecutive_order(2, 1)
    assert str(caught.value) == (
        "Expected items to contain (2, 1) in consecutive order, "
        "but 1 was not there in that order: [1, 2, 3]."
    )


def test_does_not_contain_in_consecutive_order() -> None:
    expect([1, 9, 2]).does_not_contain_in_consecutive_order(1, 2)
    items = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).does_not_contain_in_consecutive_order(2, 3)
    assert str(caught.value) == (
        "Expected items not to contain (2, 3) in consecutive order, "
        "but they ran from index 1: [1, 2, 3]."
    )


def test_contains_items_of_type_means_all_of_them() -> None:
    """FluentAssertions' `ContainItemsAssignableTo<T>` is about every item, not merely one.

    The weaker reading -- "holds some items of that type" -- would let a call
    migrated from there pass on a collection FluentAssertions rejects, which is
    the one direction a library of assertions may not drift in.
    """
    expect(["a", "b"]).contains_items_of_type(str)
    mixed: list[object] = [1, "a"]
    with pytest.raises(AssertionFailure) as caught:
        expect(mixed).contains_items_of_type(str)
    assert str(caught.value) == (
        "Expected mixed to contain only instances of str, but 1 at index 0 was int."
    )


def test_contains_items_of_type_is_the_alias_all_are_instance_of_is() -> None:
    """Same assertion, two spellings -- so they cannot report different things."""
    pets: list[object] = [Dog(), "not a pet"]
    with pytest.raises(AssertionFailure) as by_alias:
        expect(pets).contains_items_of_type(Animal)
    with pytest.raises(AssertionFailure) as by_name:
        expect(pets).all_are_instance_of(Animal)
    assert str(by_alias.value) == str(by_name.value)


def test_does_not_contain_items_of_type_points_at_the_index() -> None:
    """Declared on the collection subject; a sequence still says *where*."""
    expect([1, 2]).does_not_contain_items_of_type(str)
    mixed: list[object] = [1, "a"]
    with pytest.raises(AssertionFailure) as caught:
        expect(mixed).does_not_contain_items_of_type(str)
    assert str(caught.value) == (
        "Expected mixed not to contain any item of type str, but 'a' at index 1 was str."
    )


def test_does_not_contain_none() -> None:
    expect([1, 2]).does_not_contain_none()
    items: list[int | None] = [1, None]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).does_not_contain_none()
    assert str(caught.value) == (
        "Expected items not to contain None, but found one at index 1: [1, None]."
    )


def test_does_not_contain_none_with_a_key_points_at_the_index() -> None:
    rows = [Row(1, "ana@example.com"), Row(2, None)]
    expect(rows).does_not_contain_none()
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).does_not_contain_none(key=email_of)
    assert str(caught.value) == (
        "Expected rows not to contain None under email_of,"
        " but Row(2) at index 1 gave one: [Row(1), Row(2)]."
    )


def test_has_unique_items_and_its_alias() -> None:
    expect([1, 2, 3]).has_unique_items()
    expect([1, 2, 3]).contains_no_duplicates()
    items = [1, 2, 1]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).has_unique_items()
    assert str(caught.value) == (
        "Expected items to have unique items, but 1 appeared again at index 2: [1, 2, 1]."
    )
    with pytest.raises(AssertionFailure) as caught:
        expect(items).contains_no_duplicates()
    assert str(caught.value) == (
        "Expected items to have unique items, but 1 appeared again at index 2: [1, 2, 1]."
    )


def test_has_unique_items_copes_with_unhashable_items() -> None:
    """A list of dicts is an ordinary test subject; refusing to check it is not an option."""
    expect([{"a": 1}, {"a": 2}]).has_unique_items()
    rows = [{"a": 1}, {"a": 1}]
    with pytest.raises(AssertionFailure, match="appeared again at index 1"):
        expect(rows).has_unique_items()


def test_has_unique_items_with_a_key_names_the_id_and_the_index() -> None:
    """The whole row would bury the finding; the index says which one collided."""
    rows = [Row(1, "a"), Row(2, "b"), Row(1, "c")]
    expect(rows).has_unique_items()
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).has_unique_items(key=row_id)
    assert str(caught.value) == (
        "Expected rows to have unique items by row_id,"
        " but 1 appeared again at index 2: [Row(1), Row(2), Row(1)]."
    )


# ---------------------------------------------------------------------------
# Find by predicate: the positional half of an inherited assertion
# ---------------------------------------------------------------------------
def test_contains_matching_continues_on_the_first_item_that_matched() -> None:
    """ "First" is a real claim here, where on an unordered subject it is not."""
    subject = expect([1, 2, 4])
    found = subject.contains_matching(is_even)
    assert found.subject == 2
    assert found.and_ is subject
    found.which.is_equal_to(2)


def test_contains_matching_finds_the_row_then_asserts_on_it() -> None:
    """The three-statement pattern the assertion exists to collapse."""
    rows = [Row(1, "ana@example.com"), Row(2, None)]
    expect(rows).extracting(email_of).contains_matching(lambda email: email is None)
    expect(rows).contains_matching(lambda row: row.id == 2).which.is_same_as(rows[1])


def test_does_not_contain_matching_points_at_the_index() -> None:
    expect([1, 3]).does_not_contain_matching(is_even)
    items = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).does_not_contain_matching(is_even)
    assert str(caught.value) == (
        "Expected items not to contain an item matching is_even, but 2 at index 1 did."
    )


def test_contains_single_matching_points_at_the_matches_it_rejected() -> None:
    expect([1, 2, 3]).contains_single_matching(is_even)
    items = [1, 2, 3, 4]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).contains_single_matching(is_even)
    assert str(caught.value) == (
        "Expected items to contain exactly one item matching is_even,"
        " but 2 items of 4 matched: [2, 4]."
    )


# ---------------------------------------------------------------------------
# Multi-item membership
# ---------------------------------------------------------------------------
def test_the_multi_item_family_reads_the_same_as_it_does_on_a_collection() -> None:
    """Declared one class up; a sequence adds nothing, and must take nothing away."""
    expect([1, 2, 3]).contains_all(1, 3).and_.contains_any(9, 2)
    expect([1, 2]).does_not_contain_all(1, 9)
    items = [1, 2]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).contains_all(1, 9)
    assert str(caught.value) == ("Expected items to contain all of (1, 9), but was missing [9].")


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------
def test_a_sequence_too_short_to_be_out_of_order_is_sorted() -> None:
    expect(EMPTY).is_sorted()
    expect([7]).is_sorted()
    expect(EMPTY).is_sorted_descending()
    expect([7]).is_sorted_descending()


def test_is_sorted_allows_equal_neighbours() -> None:
    expect([1, 1, 2]).is_sorted()
    expect([2, 1, 1]).is_sorted_descending()


def test_is_sorted_names_the_pair_that_broke_the_order() -> None:
    scores = [3, 5, 1]
    with pytest.raises(AssertionFailure) as caught:
        expect(scores).is_sorted()
    assert str(caught.value) == (
        "Expected scores to be sorted, but 1 at index 2 came after 5: [3, 5, 1]."
    )


def test_is_sorted_takes_a_key() -> None:
    expect(["a", "bb", "ccc"]).is_sorted(key=len)
    words = ["ccc", "a"]
    with pytest.raises(AssertionFailure) as caught:
        expect(words).is_sorted(key=len)
    assert str(caught.value) == (
        "Expected words to be sorted, but 'a' at index 1 came after 'ccc': ['ccc', 'a']."
    )


def test_is_not_sorted() -> None:
    expect([3, 1]).is_not_sorted()
    scores = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(scores).is_not_sorted()
    assert str(caught.value) == "Expected scores not to be sorted, but it was: [1, 2, 3]."


def test_is_sorted_descending() -> None:
    expect([3, 2, 1]).is_sorted_descending()
    expect([1, 3, 2]).is_not_sorted_descending()
    scores = [1, 2]
    with pytest.raises(AssertionFailure) as caught:
        expect(scores).is_sorted_descending()
    assert str(caught.value) == (
        "Expected scores to be sorted in descending order, but 2 at index 1 came after 1: [1, 2]."
    )


def test_is_not_sorted_descending() -> None:
    scores = [3, 1]
    with pytest.raises(AssertionFailure) as caught:
        expect(scores).is_not_sorted_descending()
    assert str(caught.value) == (
        "Expected scores not to be sorted in descending order, but it was: [3, 1]."
    )


# ---------------------------------------------------------------------------
# Element types
# ---------------------------------------------------------------------------
def test_all_are_instance_of_accepts_subclasses() -> None:
    expect([Dog(), Animal()]).all_are_instance_of(Animal)
    pets: list[object] = [Dog(), "not a pet"]
    with pytest.raises(AssertionFailure) as caught:
        expect(pets).all_are_instance_of(Animal)
    assert str(caught.value) == (
        "Expected pets to contain only instances of Animal, but 'not a pet' at index 1 was str."
    )


def test_all_are_exactly_type_rejects_subclasses() -> None:
    expect([Animal(), Animal()]).all_are_exactly_type(Animal)
    pets: list[Animal] = [Animal(), Dog()]
    with pytest.raises(AssertionFailure) as caught:
        expect(pets).all_are_exactly_type(Animal)
    assert str(caught.value) == (
        "Expected pets to contain only Animal exactly, but Dog() at index 1 was Dog."
    )


def test_all_equal_to() -> None:
    expect([2, 2]).all_equal_to(2)
    items = [2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).all_equal_to(2)
    assert str(caught.value) == (
        "Expected items to contain only 2, but 3 at index 1 did not match: [2, 3]."
    )


# ---------------------------------------------------------------------------
# Nested assertions
# ---------------------------------------------------------------------------
def test_all_satisfy_passes_and_chains() -> None:
    subject = expect([2, 4])
    assert subject.all_satisfy(lambda value: expect(value).is_greater_than(1)) is subject


def test_all_satisfy_reports_every_failing_item_with_its_index() -> None:
    def is_two(value: int) -> None:
        expect(value).is_equal_to(2)

    items = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).all_satisfy(is_two)
    message = str(caught.value)
    assert message.startswith("Expected items to satisfy the inspection for every item.\n")
    assert "  - at index 0: Expected value to equal 2, but was 1" in message
    assert "  - at index 2: Expected value to equal 2, but was 3" in message
    assert "index 1" not in message


def test_all_satisfy_lets_a_real_error_through() -> None:
    """A broken inspector is a bug in the test, not a finding about the subject."""
    with pytest.raises(ZeroDivisionError):
        expect([1, 2]).all_satisfy(lambda value: value / 0)


def test_satisfies_respectively_pairs_items_with_assertions() -> None:
    expect([1, 2]).satisfies_respectively(
        lambda value: expect(value).is_equal_to(1),
        lambda value: expect(value).is_equal_to(2),
    )


def test_satisfies_respectively_requires_matching_counts() -> None:
    def is_one(value: int) -> None:
        expect(value).is_equal_to(1)

    items = [1, 2]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).satisfies_respectively(is_one)
    assert str(caught.value) == (
        "Expected items to have one item for each of the 1 assertion, but had 2: [1, 2]."
    )


def test_satisfies_respectively_tags_findings_with_their_index() -> None:
    def is_one(value: int) -> None:
        expect(value).is_equal_to(1)

    def is_nine(value: int) -> None:
        expect(value).is_equal_to(9)

    items = [1, 2]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).satisfies_respectively(is_one, is_nine)
    message = str(caught.value)
    assert message.startswith("Expected items to satisfy its assertions respectively.\n")
    assert "  - at index 1: Expected value to equal 9, but was 2" in message


def test_satisfies_in_any_order_matches_predicates_to_distinct_items() -> None:
    expect([1, 2]).satisfies_in_any_order(lambda value: value == 2, lambda value: value == 1)


def test_satisfies_in_any_order_is_not_greedy() -> None:
    """The case a naive `any()` per predicate gets wrong.

    Both predicates accept ``1``, and only the first accepts ``2``. Testing them
    independently passes twice over the same item; the assignment that actually
    exists is the first predicate to ``2`` and the second to ``1``.
    """
    expect([1, 2]).satisfies_in_any_order(lambda value: value in (1, 2), lambda value: value == 1)


def test_satisfies_in_any_order_reports_the_predicate_left_unmatched() -> None:
    def is_one(value: int) -> bool:
        return value == 1

    items = [1, 2]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).satisfies_in_any_order(is_one, is_one)
    assert str(caught.value) == (
        "Expected items to satisfy every predicate in any order, "
        "but no unclaimed item matched is_one (predicate 2): [1, 2]."
    )


def test_satisfies_in_any_order_requires_matching_counts() -> None:
    items = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(items).satisfies_in_any_order(lambda value: value == 1)
    assert str(caught.value) == (
        "Expected items to have one item for each of the 1 predicate, but had 3: [1, 2, 3]."
    )


# ---------------------------------------------------------------------------
# Wildcard matching
# ---------------------------------------------------------------------------
def test_contains_match_uses_wildcards() -> None:
    expect(["alpha", "beta"]).contains_match("al*")
    expect(["alpha", "beta"]).contains_match("bet?")
    lines = ["alpha", "beta"]
    with pytest.raises(AssertionFailure) as caught:
        expect(lines).contains_match("gam*")
    assert str(caught.value) == (
        "Expected lines to contain a match for 'gam*', but was ['alpha', 'beta']."
    )


def test_contains_match_is_case_sensitive() -> None:
    lines = ["alpha"]
    with pytest.raises(AssertionFailure, match="to contain a match for 'AL\\*'"):
        expect(lines).contains_match("AL*")


def test_does_not_contain_match_points_at_the_item() -> None:
    expect(["alpha"]).does_not_contain_match("bet*")
    lines = ["alpha", "beta"]
    with pytest.raises(AssertionFailure) as caught:
        expect(lines).does_not_contain_match("bet*")
    assert str(caught.value) == (
        "Expected lines not to contain a match for 'bet*', but 'beta' at index 1 matched."
    )


# ---------------------------------------------------------------------------
# Rendering: long collections are capped
# ---------------------------------------------------------------------------
def test_a_long_collection_is_truncated_in_the_message() -> None:
    numbers = list(range(30))
    with pytest.raises(AssertionFailure) as caught:
        expect(numbers).is_empty()
    assert str(caught.value) == (
        "Expected numbers to be empty, but was [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, ... (20 more)]."
    )


def test_a_collection_at_the_limit_is_shown_in_full() -> None:
    numbers = list(range(10))
    with pytest.raises(AssertionFailure) as caught:
        expect(numbers).is_empty()
    assert str(caught.value) == (
        "Expected numbers to be empty, but was [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]."
    )


def test_truncation_reaches_the_argument_as_well_as_the_subject() -> None:
    """The other collection in the message is rendered by the same capped helper."""
    numbers = [0]
    with pytest.raises(AssertionFailure) as caught:
        expect(numbers).equals_sequence(list(range(12)))
    assert str(caught.value) == (
        "Expected numbers to equal [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, ... (2 more)], "
        "but had 1 item, not 12."
    )


def test_nested_findings_are_capped_the_way_collections_are() -> None:
    """A failing inspection over a long list must not print a line per item."""
    items = list(range(25))
    with pytest.raises(AssertionFailure) as caught:
        expect(items).all_satisfy(lambda value: expect(value).is_equal_to(-1))
    message = str(caught.value)
    assert "  - at index 9: Expected the value to equal -1, but was 9" in message
    assert "index 10" not in message
    # The sentence ends on the first line; the block of findings after it carries
    # no terminator of its own.
    assert message.endswith("  - ... (15 more items failed)")


# ---------------------------------------------------------------------------
# Chaining
# ---------------------------------------------------------------------------
def test_a_chain_keeps_returning_the_same_subject() -> None:
    subject = expect([1, 2, 3])
    assert subject.is_not_empty().and_.has_length(3).and_.contains(2) is subject
    assert subject.subject == [1, 2, 3]


def test_narrowing_assertions_hand_back_the_element() -> None:
    """``.which`` gives ``Expect[E]``: the element, re-typed but not re-specialised."""
    assert expect([["a"]]).contains_single().which.is_equal_to(["a"]).subject == ["a"]
    assert expect([["a"]]).contains_single().and_.has_length(1).subject == [["a"]]


# ---------------------------------------------------------------------------
# extracting: the override that re-earns the ordered catalogue
# ---------------------------------------------------------------------------
def test_extracting_keeps_the_order_of_the_source() -> None:
    """A sequence has one, extraction preserves it item for item, so ``is_sorted`` is honest."""
    rows = [Row(3, "c"), Row(1, "a"), Row(2, "b")]
    expect(rows).extracting(row_id).equals_sequence([3, 1, 2])
    expect(rows).extracting(row_id).is_not_sorted()
    expect(sorted(rows, key=row_id)).extracting(row_id).is_sorted()


def test_extracting_from_a_sequence_hands_back_a_sequence_subject() -> None:
    """The override, and the reason for it: ``CollectionExpect`` returns the order-free one."""
    subject = expect([Row(1, "a")]).extracting(row_id)
    assert isinstance(subject, SequenceExpect)
    subject.has_element_at(0, 1)


def test_extracting_reports_against_the_extracted_values() -> None:
    """The finding is about the ids, and the subject name is still the source variable.

    Name recovery reads the source line and finds ``expect(rows)`` on it, so
    the message says ``rows`` while reporting about the extracted ids. That is
    the honest outcome and the useful one -- ``rows`` is the name the reader can
    go and look at, and the alternative on that line is the "the value" fallback.
    Pinned so that a future change to it has to be deliberate.
    """
    rows = [Row(1, "a"), Row(2, "b")]
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).extracting(row_id).equals_sequence([1, 9])
    assert str(caught.value) == (
        "Expected rows to equal [1, 9], but differed at index 1 (2 instead of 9)."
    )


def test_extracting_can_be_chained_and_keeps_its_element_type() -> None:
    rows = [Row(1, "a"), Row(22, "b")]
    expect(rows).extracting(row_id).extracting(str).equals_sequence(["1", "22"])


def test_extracting_keeps_an_explicitly_given_subject_name() -> None:
    """The loop is the case an explicit subject name exists for.

    Recovery names ``batch`` every time round, which is why the name is given
    explicitly; a transformation that discarded it would hand back exactly the
    unusable message the caller had already paid to avoid.
    """
    batches = [[Row(1, "a")], [Row(2, "b")]]
    for index, batch in enumerate(batches):
        with pytest.raises(AssertionFailure) as caught:
            expect(batch, name=f"batches[{index}]").extracting(row_id).equals_sequence([9])
        assert str(caught.value).startswith(f"Expected batches[{index}] to equal [9]")


def test_extracting_takes_no_because_because_it_asserts_nothing() -> None:
    """``because`` belongs to assertions; a transformation makes no claim and cannot fail.

    Asked of a bound method: a signature read off the unsubscripted class leaves
    ``E`` unsolved and is partially unknown, which pyright's strict mode rejects.
    """
    assert "because" not in inspect.signature(expect([1]).extracting).parameters


# ---------------------------------------------------------------------------
# A passing assertion never reaches the failure path
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("no_failure_machinery")
def test_passing_sequence_assertions_never_touch_the_failure_path() -> None:
    """The nested-assertion pair is absent on purpose.

    ``all_satisfy`` and ``satisfies_respectively`` route their inner assertions
    through the collector by design, so they are the two that legitimately read
    the ``ContextVar`` on the way past.
    """
    items = [1, 2, 3]
    expect(items).is_not_empty().and_.has_length(3)
    expect(EMPTY).is_empty().and_.is_none_or_empty()
    expect(items).is_not_none_or_empty().and_.does_not_have_length(2)
    expect(items).has_length_matching(lambda count: count == 3)
    expect(items).has_length_greater_than(2).and_.has_length_greater_than_or_equal_to(3)
    expect(items).has_length_less_than(4).and_.has_length_less_than_or_equal_to(3)
    expect(items).has_same_length_as("abc").and_.does_not_have_same_length_as([1])
    expect(items).equals_sequence([1, 2, 3]).and_.does_not_equal_sequence([3, 2, 1])
    expect([1.0]).equals_approximately([1.05], tol=0.1)
    expect(items).starts_with_sequence([1]).and_.ends_with_sequence([3])
    expect(items).contains(2).and_.does_not_contain(9)
    expect(items).is_sorted().and_.is_not_sorted_descending()
    expect(items).is_sorted_descending(key=lambda value: -value).and_.is_not_sorted(key=negated)
    expect(items).has_unique_items().and_.contains_no_duplicates()
    expect(items).does_not_contain_none().and_.contains_items_of_type(int)
    expect(items).is_subset_of([1, 2, 3]).and_.intersects([3])
    expect(items).is_not_subset_of([1]).and_.does_not_intersect([9])
    expect(items).contains_in_order(1, 3).and_.contains_in_consecutive_order(1, 2)
    expect(items).does_not_contain_in_order(3, 1)
    expect(items).does_not_contain_in_consecutive_order(1, 3)
    expect(items).all_are_instance_of(int).and_.only_contains(lambda value: value > 0)
    expect(items).all_are_exactly_type(int)
    expect([2, 2]).all_equal_to(2)
    expect(items).satisfies_in_any_order(
        lambda value: value == 1, lambda value: value == 2, lambda value: value == 3
    )
    expect([7]).contains_single()
    expect(items).has_element_at(0, 1)
    expect(["a"]).contains_match("?").and_.does_not_contain_match("bb*")
    expect(items).contains_all(1, 2).and_.contains_any(3, 9)
    expect(items).does_not_contain_all(1, 9)
    expect(items).does_not_contain_items_of_type(str)
    expect(items).contains_matching(is_even).and_.does_not_contain_matching(lambda v: v > 9)
    expect([2, 3]).contains_single_matching(is_even)
    expect(items).has_unique_items(key=negated).and_.contains_no_duplicates(key=negated)
    expect(items).does_not_contain_none(key=negated)
    expect(items).extracting(negated).is_sorted_descending()


# ---------------------------------------------------------------------------
# Values a comparison cannot answer for
# ---------------------------------------------------------------------------
# A NaN is equal to nothing and ordered against nothing, and a type is free to
# write an `__eq__` that answers no -- or refuses to answer at all. Every one of
# those makes a comparison return `False` without meaning "no", and an assertion
# that reads that as agreement passes vacuously. The tell is an assertion and its
# negation *both* passing on one subject, so the pairs are asserted together
# throughout: whatever the answer is, exactly one of the two has to give it.
NAN: Final = float("nan")

#: The clause an ordering failure carries when a NaN is why it could not answer.
#: Spelled out once here; `test_the_nan_ordering_note_is_the_wording_the_ordered_subject_uses`
#: below is what ties this copy to the wording the library actually uses.
NAN_ORDERING_NOTE: Final = " (a NaN compares false against every ordering)"


class NeverEqual:
    """A type whose ``__eq__`` always says no -- not even to itself.

    A NaN with the float arithmetic taken away, so the rule can be tested on a
    value that reaches none of the numeric special cases.
    """

    __slots__ = ()

    def __eq__(self, other: object) -> bool:
        return False

    def __hash__(self) -> int:
        return 0

    def __repr__(self) -> str:
        return "NeverEqual()"


class RefusesToCompare:
    """A type whose ``__eq__`` raises. Identity is the only thing that can answer.

    Testing it is what pins the *order* of the rule: ``x is y or x == y`` never
    reaches ``==`` when the two sides are one object, so an item is still found
    where it sits. Between two different ones the error propagates, which is
    right -- an assertion has no verdict to give about a comparison that failed.
    """

    __slots__ = ()

    def __eq__(self, other: object) -> bool:
        message = "this type refuses to compare"
        raise TypeError(message)

    def __hash__(self) -> int:
        return 0

    def __repr__(self) -> str:
        return "RefusesToCompare()"


def always_nan(_: object) -> float:
    """A ``key=`` that puts the NaN in the key rather than in the item."""
    return NAN


# -- ordered equality --------------------------------------------------------
def test_a_sequence_equals_itself_and_its_negation_says_so() -> None:
    """The two are exact complements, for plain items and for a NaN alike.

    ``does_not_equal_sequence`` must not pass against the subject's own object
    just because one item declines to equal itself: whatever it holds, a
    sequence cannot differ from itself.
    """
    rows = [1, 2, 3]
    expect(rows).equals_sequence(rows)
    with pytest.raises(AssertionFailure):
        expect(rows).does_not_equal_sequence(rows)

    readings = [1.0, NAN, 3.0]
    expect(readings).equals_sequence(readings)
    with pytest.raises(AssertionFailure) as caught:
        expect(readings).does_not_equal_sequence(readings)
    assert str(caught.value) == ("Expected readings not to equal [1.0, nan, 3.0], but it did.")


def test_a_nan_matches_the_same_nan_in_another_sequence() -> None:
    """Not just the same list: the same NaN *object*, wherever it is held."""
    expect([1.0, NAN]).equals_sequence((1.0, NAN))
    expect([1.0, NAN, 3.0]).starts_with_sequence([1.0, NAN])
    expect([1.0, NAN, 3.0]).ends_with_sequence([NAN, 3.0])
    expect([1.0, NAN, 3.0]).has_element_at(1, NAN)


def test_two_different_nans_are_still_different_items() -> None:
    """Identity is a shortcut, not a claim that all NaNs are one value."""
    other = float("nan")
    assert other is not NAN
    readings = [NAN]
    with pytest.raises(AssertionFailure) as caught:
        expect(readings).equals_sequence([other])
    assert str(caught.value) == (
        "Expected readings to equal [nan], but differed at index 0 (nan instead of nan)."
    )
    expect(readings).does_not_equal_sequence([other])


def test_has_element_at_finds_the_item_the_caller_handed_over() -> None:
    """And hands the item itself on, not a copy that happens to compare equal."""
    found = expect([1.0, NAN, 3.0]).has_element_at(1, NAN)
    assert found.which.is_same_as(NAN).subject is NAN


# -- containment -------------------------------------------------------------
def test_the_containment_assertions_agree_about_a_nan() -> None:
    """``contains_in_order`` must not report absent what ``does_not_contain`` finds.

    One sequence, one item, two assertions insisting on opposite answers is the
    failure this rules out; the calls below are every pairing that could
    disagree, asserted to agree.
    """
    readings = [1.0, NAN, 3.0]
    expect(readings).contains(NAN)
    expect(readings).contains_in_order(NAN)
    expect(readings).contains_in_order(1.0, NAN, 3.0)
    expect(readings).contains_in_consecutive_order(NAN, 3.0)

    with pytest.raises(AssertionFailure) as caught:
        expect(readings).does_not_contain(NAN)
    assert str(caught.value) == (
        "Expected readings not to contain nan, but found it at index 1: [1.0, nan, 3.0]."
    )
    with pytest.raises(AssertionFailure):
        expect(readings).does_not_contain_in_order(NAN)
    with pytest.raises(AssertionFailure):
        expect(readings).does_not_contain_in_consecutive_order(NAN, 3.0)


def test_a_type_that_never_equals_anything_is_still_where_it_is() -> None:
    absent = NeverEqual()
    item = NeverEqual()
    items = [item, NeverEqual()]
    expect(items).contains(item)
    expect(items).contains_in_order(item)
    expect(items).contains_in_consecutive_order(*items)
    expect(items).equals_sequence(items)
    expect(items).starts_with_sequence([item])
    expect(items).ends_with_sequence([items[1]])
    expect(items).has_element_at(0, item)
    with pytest.raises(AssertionFailure):
        expect(items).does_not_contain(item)
    with pytest.raises(AssertionFailure):
        expect(items).does_not_equal_sequence(items)
    # A different instance really is absent -- identity is not a free pass.
    expect(items).does_not_contain(absent)
    expect(items).does_not_contain_in_order(absent)


def test_an_eq_that_raises_never_runs_against_the_item_itself() -> None:
    """Identity comes first, so the comparison is not reached at all."""
    item = RefusesToCompare()
    items = [item]
    expect(items).equals_sequence(items)
    expect(items).contains_in_order(item)
    expect(items).contains_in_consecutive_order(item)
    expect(items).starts_with_sequence([item])
    expect(items).ends_with_sequence([item])
    expect(items).has_element_at(0, item)


def test_an_eq_that_raises_against_a_different_item_propagates() -> None:
    """A broken comparison is a bug in the test, not a finding about the value."""
    with pytest.raises(TypeError, match="refuses to compare"):
        expect([RefusesToCompare()]).equals_sequence([RefusesToCompare()])


def test_equals_approximately_still_says_a_nan_is_close_to_nothing() -> None:
    """The one deliberate exception, pinned so it cannot be "fixed" by accident.

    Everywhere else the question is which items a sequence holds, and a NaN is
    held where it sits. Here the question is how far apart two numbers are, and
    ``is_close_to`` answers that the same way: a NaN is close to nothing, itself
    included.
    """
    readings = [1.0, NAN]
    with pytest.raises(AssertionFailure) as caught:
        expect(readings).equals_approximately(readings, tol=0.5)
    assert str(caught.value) == (
        "Expected readings to equal [1.0, nan] within 0.5, but differed at index 1"
        " (nan instead of nan) (a NaN is close to nothing, itself included)."
    )


# -- ordering ----------------------------------------------------------------
def test_is_sorted_and_is_sorted_descending_cannot_both_pass() -> None:
    """The headline symptom: two opposites agreeing that a NaN list is fine.

    ``current < previous`` asks "is this pair definitely out of order?", and a
    pair holding a NaN answers false to that in both directions. The inclusive
    spelling asks the answerable question instead.
    """
    readings = [3.0, NAN, 1.0]
    with pytest.raises(AssertionFailure) as caught:
        expect(readings).is_sorted()
    assert str(caught.value) == (
        "Expected readings to be sorted, but nan at index 1 came after 3.0"
        " (a NaN compares false against every ordering): [3.0, nan, 1.0]."
    )
    with pytest.raises(AssertionFailure) as caught:
        expect(readings).is_sorted_descending()
    assert str(caught.value) == (
        "Expected readings to be sorted in descending order, but nan at index 1 came after 3.0"
        " (a NaN compares false against every ordering): [3.0, nan, 1.0]."
    )
    expect(readings).is_not_sorted()
    expect(readings).is_not_sorted_descending()


@pytest.mark.parametrize(
    ("readings", "index"),
    [
        pytest.param([NAN, 1.0, 2.0], 1, id="first"),
        pytest.param([1.0, NAN, 2.0], 1, id="middle"),
        pytest.param([1.0, 2.0, NAN], 2, id="last"),
        pytest.param([1.0, NAN, NAN, 2.0], 1, id="several-reported-at-the-first"),
        pytest.param([NAN, NAN], 1, id="all-nan"),
    ],
)
def test_is_sorted_reports_a_nan_where_it_breaks_the_order(
    readings: "Sequence[float]", index: int
) -> None:
    """Wherever it sits, and reported once -- at the first pair that cannot answer.

    Each list is otherwise ascending, so the NaN is the only thing there is to
    find and the index it is reported at is not a coincidence.
    """
    with pytest.raises(AssertionFailure) as caught:
        expect(readings).is_sorted()
    assert f"at index {index}" in str(caught.value)
    assert NAN_ORDERING_NOTE in str(caught.value)
    expect(readings).is_not_sorted()


@pytest.mark.parametrize(
    ("readings", "index"),
    [
        pytest.param([NAN, 2.0, 1.0], 1, id="first"),
        pytest.param([2.0, NAN, 1.0], 1, id="middle"),
        pytest.param([2.0, 1.0, NAN], 2, id="last"),
        pytest.param([2.0, NAN, NAN, 1.0], 1, id="several-reported-at-the-first"),
        pytest.param([NAN, NAN], 1, id="all-nan"),
    ],
)
def test_is_sorted_descending_reports_a_nan_where_it_breaks_the_order(
    readings: "Sequence[float]", index: int
) -> None:
    """The mirror of the ascending case, on lists that are otherwise descending."""
    with pytest.raises(AssertionFailure) as caught:
        expect(readings).is_sorted_descending()
    assert f"at index {index}" in str(caught.value)
    assert NAN_ORDERING_NOTE in str(caught.value)
    expect(readings).is_not_sorted_descending()


def test_one_nan_on_its_own_is_sorted_and_nothing_is_out_of_place() -> None:
    """A single item holds no pair, so there is nothing an ordering could break."""
    expect([NAN]).is_sorted()
    expect([NAN]).is_sorted_descending()
    with pytest.raises(AssertionFailure):
        expect([NAN]).is_not_sorted()
    with pytest.raises(AssertionFailure):
        expect([NAN]).is_not_sorted_descending()


def test_an_empty_sequence_is_sorted_both_ways() -> None:
    """No pair, no finding -- unchanged by the NaN rule, and pinned as such."""
    expect(EMPTY).is_sorted()
    expect(EMPTY).is_sorted_descending()
    with pytest.raises(AssertionFailure):
        expect(EMPTY).is_not_sorted()
    with pytest.raises(AssertionFailure):
        expect(EMPTY).is_not_sorted_descending()


def test_a_key_that_returns_a_nan_is_reported_too() -> None:
    """Neither rendered item is a NaN, which is exactly why the note has to be there."""
    words = ["a", "bb"]
    with pytest.raises(AssertionFailure) as caught:
        expect(words).is_sorted(key=always_nan)
    assert str(caught.value) == (
        "Expected words to be sorted, but 'bb' at index 1 came after 'a'"
        " (a NaN compares false against every ordering): ['a', 'bb']."
    )
    expect(words).is_not_sorted(key=always_nan)


def test_a_decimal_nan_signals_rather_than_being_reported() -> None:
    """Left to propagate, the position ``_ordered.py`` states and explains.

    An ordering against a quiet ``Decimal`` NaN raises rather than answering
    false, so there is no vacuous pass to fix -- and catching it would mean
    catching what a user's own incomparable type raises for real reasons.
    """
    from decimal import Decimal, InvalidOperation

    readings = [Decimal("1"), Decimal("NaN")]
    with pytest.raises(InvalidOperation):
        expect(readings).is_sorted()
    with pytest.raises(InvalidOperation):
        expect(readings).is_sorted_descending()
    with pytest.raises(InvalidOperation):
        expect(readings).is_not_sorted()
    with pytest.raises(InvalidOperation):
        expect(readings).is_not_sorted_descending()


def test_equal_neighbours_are_still_in_order_both_ways() -> None:
    """The inclusive spelling must not turn a tie into a violation."""
    expect([1, 1, 2]).is_sorted()
    expect([2, 1, 1]).is_sorted_descending()
    expect([1, 1, 1]).is_sorted().and_.is_sorted_descending()
    with pytest.raises(AssertionFailure):
        expect([1, 1, 1]).is_not_sorted()
    with pytest.raises(AssertionFailure):
        expect([1, 1, 1]).is_not_sorted_descending()


def test_the_nan_ordering_note_is_the_wording_the_ordered_subject_uses() -> None:
    """One finding, one phrasing, whichever subject reported it.

    The note is restated in ``_sequence`` rather than imported, because the name
    is private to ``_ordered``. This is what keeps the copy honest.
    """
    from lovely_assertions import _ordered

    stated = _pairs._NAN_ORDERING_NOTE  # pyright: ignore[reportPrivateUsage]
    assert stated == _ordered._NAN_OPERAND_NOTE  # pyright: ignore[reportPrivateUsage]
    assert stated == NAN_ORDERING_NOTE


class OnlyLessThan:
    """The whole of what an ordering assertion asks of a value.

    ``__lt__`` and nothing else -- what ``sorted()``, ``min()`` and ``bisect``
    require, and the literal text of the ``_Ordered`` protocol and of what the
    published ``key=`` signatures promise: "anything ``<`` accepts". ``==`` falls
    back to identity, as it does on any class that does not define it.
    """

    __slots__ = ("rank",)

    def __init__(self, rank: int) -> None:
        self.rank = rank

    def __lt__(self, other: "OnlyLessThan") -> bool:
        return self.rank < other.rank

    def __repr__(self) -> str:
        return f"OnlyLessThan({self.rank})"


def test_ordering_asks_for_no_operator_beyond_the_one_sorted_needs() -> None:
    """A ``__lt__``-only element is ordered, not a ``TypeError``.

    Spelling the ordering test with ``<=`` and ``>=`` reads well and quietly
    widens what an element has to provide: ``a <= b`` on a class that defines
    only ``__lt__`` has no reflected fallback left and raises. Every ordering
    assertion in the catalogue would then fail on a type ``sorted()`` handles
    without complaint -- and on the exact type the published protocol describes.
    """
    ascending = [OnlyLessThan(1), OnlyLessThan(2), OnlyLessThan(3)]
    assert sorted(ascending) == ascending
    expect(ascending).is_sorted()
    expect(ascending).is_not_sorted_descending()
    with pytest.raises(AssertionFailure):
        expect(ascending).is_not_sorted()
    with pytest.raises(AssertionFailure) as caught:
        expect(ascending).is_sorted_descending()
    assert str(caught.value) == (
        "Expected ascending to be sorted in descending order, but OnlyLessThan(2)"
        " at index 1 came after OnlyLessThan(1): [OnlyLessThan(1), OnlyLessThan(2),"
        " OnlyLessThan(3)]."
    )

    descending = [OnlyLessThan(3), OnlyLessThan(2), OnlyLessThan(1)]
    expect(descending).is_sorted_descending()
    expect(descending).is_not_sorted()


def test_a_key_returning_a_lt_only_value_is_ordered_too() -> None:
    """The ``key=`` half of the same promise -- that is where ``_Ordered`` is named."""
    expect([1, 2, 3]).is_sorted(key=OnlyLessThan)
    expect([3, 2, 1]).is_sorted_descending(key=OnlyLessThan)
    with pytest.raises(AssertionFailure):
        expect([1, 2, 3]).is_sorted_descending(key=OnlyLessThan)


# ---------------------------------------------------------------------------
# because reaches all of them
# ---------------------------------------------------------------------------
#: One failing call per assertion **this class declares**, used twice: to prove
#: every one of them carries the caller's `because` reason into its message, and
#: to prove the table itself has not fallen behind the catalogue. Each `id` is
#: the method's real name, which is what makes the second test possible.
#:
#: The order-free half of the catalogue is declared on `CollectionExpect` and its
#: `because` coverage lives in `tests/test_collection.py`, next to the class that
#: declares it. `does_not_contain` appears in both tables because both classes
#: declare it: the sequence override exists to report the index.
BECAUSE_CALLS: Final = [
    pytest.param(lambda: expect([1]).equals_sequence([2], because="R"), id="equals_sequence"),
    pytest.param(
        lambda: expect([1]).does_not_equal_sequence([1], because="R"),
        id="does_not_equal_sequence",
    ),
    pytest.param(
        lambda: expect([1.0]).equals_approximately([2.0], tol=0.1, because="R"),
        id="equals_approximately",
    ),
    pytest.param(
        lambda: expect([1]).starts_with_sequence([2], because="R"), id="starts_with_sequence"
    ),
    pytest.param(lambda: expect([1]).ends_with_sequence([2], because="R"), id="ends_with_sequence"),
    pytest.param(lambda: expect([1]).has_element_at(0, 2, because="R"), id="has_element_at"),
    pytest.param(lambda: expect([1]).does_not_contain(1, because="R"), id="does_not_contain"),
    pytest.param(lambda: expect([1]).contains_in_order(2, because="R"), id="contains_in_order"),
    pytest.param(
        lambda: expect([1]).does_not_contain_in_order(1, because="R"),
        id="does_not_contain_in_order",
    ),
    pytest.param(
        lambda: expect([1]).contains_in_consecutive_order(2, because="R"),
        id="contains_in_consecutive_order",
    ),
    pytest.param(
        lambda: expect([1]).does_not_contain_in_consecutive_order(1, because="R"),
        id="does_not_contain_in_consecutive_order",
    ),
    pytest.param(lambda: expect([2, 1]).is_sorted(because="R"), id="is_sorted"),
    pytest.param(lambda: expect([1, 2]).is_not_sorted(because="R"), id="is_not_sorted"),
    pytest.param(
        lambda: expect([1, 2]).is_sorted_descending(because="R"), id="is_sorted_descending"
    ),
    pytest.param(
        lambda: expect([2, 1]).is_not_sorted_descending(because="R"),
        id="is_not_sorted_descending",
    ),
    pytest.param(
        lambda: expect([1]).satisfies_respectively(because="R"), id="satisfies_respectively"
    ),
]


#: Public methods that are **not** assertions: they make no claim, so they cannot
#: fail and have no `because` to carry -- only an assertion takes one. Listed
#: rather than detected, so that adding a second one is a deliberate act.
NOT_ASSERTIONS: Final = frozenset({"extracting"})


@pytest.mark.parametrize("call", BECAUSE_CALLS)
def test_because_reaches_every_assertion(call: object) -> None:
    with pytest.raises(AssertionFailure, match="because R"):
        call()  # type: ignore[operator]  # pyright: ignore[reportCallIssue]


def test_the_because_table_has_not_fallen_behind_the_catalogue() -> None:
    """A new assertion must arrive with its `because` case, or this fails.

    The table above is only worth having if it cannot quietly go stale: without
    this, an assertion added next month gets no coverage at all and nothing says
    so. `vars()` rather than `dir()` on purpose -- the inherited half of the
    surface belongs to `Expect` and is covered by its own tests.
    """
    covered = {parameters.id for parameters in BECAUSE_CALLS}
    declared = {
        name
        for name, attribute in declared_by_the_subject(SequenceExpect).items()
        if not name.startswith("_") and callable(attribute)
    } - NOT_ASSERTIONS
    assert covered == declared


def test_everything_excused_from_the_because_table_really_is_declared() -> None:
    """The excuse list cannot outlive what it excuses, or it starts hiding regressions."""
    assert set(declared_by_the_subject(SequenceExpect)) >= NOT_ASSERTIONS
