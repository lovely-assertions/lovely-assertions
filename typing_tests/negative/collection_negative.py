"""Every marked line here must be rejected by pyright and mypy.

The first block is the whole reason the subject exists. ``expect({1, 2}).is_sorted()``
is not a slow assertion or an awkward one: a set has no order, so the question has
no answer, and a library that sells typed discoverability has to make it *not
compile*. Runtime tests cannot prove that -- an assertion that raises
``TypeError: 'set' object is not subscriptable`` passes any test that expects an
error. Only a checker can, and only this file makes the checker's verdict a
tested one.

The rest is the usual insurance: without it, `typing_tests/positive/collection.py`
proves nothing, because a subject that had quietly collapsed to `Any` would
satisfy every `assert_type` in it.
"""

from typing import assert_type

from lovely_assertions import Expect, Found, SequenceExpect, expect

# Also exported from the package root; either spelling reaches the same class.
from lovely_assertions._collection import CollectionExpect


def the_ordered_catalogue_is_out_of_reach(tags: set[int]) -> None:
    """The order-dependent half of the sequence catalogue, one line each."""
    subject = CollectionExpect[int](tags)
    subject.is_sorted()  # expect-error: a set has no order to be in
    subject.is_not_sorted()  # expect-error
    subject.is_sorted_descending()  # expect-error
    subject.is_not_sorted_descending()  # expect-error
    subject.equals_sequence([1, 2])  # expect-error: "same items, same order"
    subject.does_not_equal_sequence([1, 2])  # expect-error
    subject.equals_approximately([1.0], tol=0.1)  # expect-error
    subject.starts_with_sequence([1])  # expect-error: nothing starts a set
    subject.ends_with_sequence([1])  # expect-error
    subject.has_element_at(0, 1)  # expect-error: there is no index 0
    subject.contains_in_order(1, 2)  # expect-error
    subject.does_not_contain_in_order(1, 2)  # expect-error
    subject.contains_in_consecutive_order(1, 2)  # expect-error
    subject.does_not_contain_in_consecutive_order(1, 2)  # expect-error
    subject.satisfies_respectively(lambda value: expect(value).is_equal_to(1))  # expect-error


def the_two_subjects_are_not_interchangeable(tags: set[int], items: list[int]) -> None:
    """A sequence is a collection; a collection is not a sequence."""
    widened: CollectionExpect[int] = expect(items)
    narrowed: SequenceExpect[int] = CollectionExpect[int](tags)  # expect-error
    _ = (widened, narrowed)


def the_subject_stays_specialised(tags: set[int]) -> None:
    subject = CollectionExpect[int](tags)
    assert_type(subject, Expect[set[int]])  # expect-error
    assert_type(subject.is_empty(), Expect[set[int]])  # expect-error
    assert_type(subject.subject, set[int])  # expect-error: `.subject` is the ABC


def the_element_type_is_enforced(tags: set[int], words: set[str]) -> None:
    subject = CollectionExpect[int](tags)
    subject.contains("x")  # expect-error: not an element type
    subject.does_not_contain("x")  # expect-error
    subject.all_equal_to("x")  # expect-error
    subject.contains_only(1, "x")  # expect-error
    subject.contains_none_of("x")  # expect-error
    subject.contains_all(1, "x")  # expect-error
    subject.does_not_contain_all("x")  # expect-error
    subject.contains_any("x")  # expect-error
    subject.is_subset_of(words)  # expect-error
    subject.is_superset_of(words)  # expect-error
    subject.is_proper_subset_of(words)  # expect-error
    subject.is_proper_superset_of(words)  # expect-error
    subject.is_disjoint_from(words)  # expect-error


def arguments_keep_their_own_types(tags: set[int]) -> None:
    subject = CollectionExpect[int](tags)
    subject.has_length("3")  # expect-error
    subject.has_length_greater_than(None)  # expect-error
    subject.has_same_length_as(3)  # expect-error: a collection, not a count
    subject.all_are_instance_of(3)  # expect-error: a type, not an instance


def because_is_keyword_only(tags: set[int]) -> None:
    CollectionExpect[int](tags).is_empty("a reason")  # expect-error: `because` is keyword-only


def predicates_receive_the_element(tags: set[int]) -> None:
    subject = CollectionExpect[int](tags)
    subject.only_contains(lambda value: value.upper())  # expect-error: not a str
    subject.satisfies_in_any_order(lambda value: value.upper())  # expect-error
    subject.contains_matching(lambda value: value.upper())  # expect-error
    subject.does_not_contain_matching(lambda value: value.upper())  # expect-error
    subject.contains_single_matching(lambda value: value.upper())  # expect-error


def keys_receive_the_element_and_are_keyword_only(tags: set[int]) -> None:
    """`key=` is the same promise `predicate` makes, and like `because` it is keyword-only."""
    subject = CollectionExpect[int](tags)
    subject.has_unique_items(key=lambda value: value.upper())  # expect-error: not a str
    subject.contains_no_duplicates(key=lambda value: value.upper())  # expect-error
    subject.does_not_contain_none(key=lambda value: value.upper())  # expect-error
    subject.has_unique_items(str)  # expect-error: `key` is keyword-only
    subject.does_not_contain_none(str)  # expect-error


def found_is_not_a_subject(tags: set[int]) -> None:
    """`.and_` or `.which` is required; `Found` carries no assertions of its own."""
    CollectionExpect[int](tags).contains_single().is_empty()  # expect-error
    CollectionExpect[int](tags).contains_matching(bool).is_empty()  # expect-error


def found_continuations_keep_their_types(tags: set[int]) -> None:
    subject = CollectionExpect[int](tags)
    assert_type(subject.contains_single(), Found[CollectionExpect[str], str])  # expect-error
    assert_type(subject.contains_single().which, CollectionExpect[int])  # expect-error
    assert_type(subject.contains_single().subject, str)  # expect-error
    assert_type(subject.contains_matching(bool), CollectionExpect[int])  # expect-error
    assert_type(subject.contains_single_matching(bool).subject, str)  # expect-error


# ---------------------------------------------------------------------------
# extracting
# ---------------------------------------------------------------------------
def extracting_takes_the_callable_form_only(tags: set[int]) -> None:
    """assertpy's ``extracting("name")`` is the spelling this library will not ship.

    A string cannot tell a checker that the attribute exists, let alone what type
    it has, so the result would be ``Any`` and every assertion downstream of it
    unchecked. This line is what makes "not offered" a tested claim rather than
    an omission.
    """
    subject = CollectionExpect[int](tags)
    subject.extracting("real")  # expect-error: the string form is untypeable
    subject.extracting(lambda value: value.upper())  # expect-error: the element is an int
    subject.extracting(len, because="a reason")  # expect-error: a transformation asserts nothing


def extracting_from_an_unordered_collection_stays_unordered(tags: set[int]) -> None:
    """The trap the return type exists to close.

    Extraction materialises a list, so a ``SequenceExpect`` return would type-check
    -- and would let ``is_sorted`` be asked of a ``set``'s iteration order, which
    is the question this whole subject split exists to make uncompilable.
    """
    extracted = CollectionExpect[int](tags).extracting(str)
    extracted.is_sorted()  # expect-error: a set's iteration order is not an order
    extracted.equals_sequence(["1"])  # expect-error
    extracted.has_element_at(0, "1")  # expect-error


def extracting_keeps_the_type_the_selector_returns(tags: set[int], items: list[int]) -> None:
    subject = CollectionExpect[int](tags)
    assert_type(subject.extracting(str), CollectionExpect[int])  # expect-error
    assert_type(subject.extracting(str), SequenceExpect[str])  # expect-error: not a sequence
    assert_type(expect(items).extracting(str), CollectionExpect[str])  # expect-error: it is one
    subject.extracting(str).contains(1)  # expect-error: the elements are strings now


def wildcard_matching_is_for_strings(tags: set[int], words: set[str]) -> None:
    numbers = CollectionExpect[int](tags)
    strings = CollectionExpect[str](words)
    numbers.contains_match("a*")  # expect-error: the elements are not strings
    numbers.does_not_contain_match("a*")  # expect-error
    strings.contains_match(3)  # expect-error: the pattern is a string
    assert_type(strings.contains_match("a*"), CollectionExpect[int])  # expect-error


class Tags(CollectionExpect[str]):
    """A subclass, to pin the half of `contains_match` that is easy to lose."""

    __slots__ = ()


def the_string_only_pair_does_not_widen_a_subclass(tags: set[str]) -> None:
    """It would be sound to hand back `CollectionExpect[str]` here, and it is wrong.

    The bound type variable exists precisely so the caller keeps the subject it
    started with; a return widened to the bound is the regression this line
    catches.
    """
    assert_type(Tags(tags).contains_match("a*"), CollectionExpect[str])  # expect-error
