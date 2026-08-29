"""Every marked line here must be rejected by pyright and mypy.

Without this half, `typing_tests/positive/sequence.py` proves nothing: a subject
that had quietly collapsed to `Any` would satisfy every `assert_type` in it. These
are the mistakes the sequence surface is supposed to catch -- the wrong element
type, the wrong continuation, a string-only assertion reached from a sequence of
something else.
"""

from typing import assert_type

from lovely_assertions import Expect, Found, SequenceExpect, expect


def the_subject_stays_specialised(items: list[int]) -> None:
    assert_type(expect(items), Expect[list[int]])  # expect-error: must be SequenceExpect
    assert_type(expect(items).is_empty(), Expect[list[int]])  # expect-error
    assert_type(expect(items).subject, list[int])  # expect-error: `.subject` is the ABC


def the_element_type_is_enforced(items: list[int], words: list[str]) -> None:
    expect(items).contains("x")  # expect-error: not an element type
    expect(items).does_not_contain("x")  # expect-error
    expect(items).all_equal_to("x")  # expect-error
    expect(items).has_element_at(0, "x")  # expect-error
    expect(items).contains_in_order(1, "x")  # expect-error
    expect(items).equals_sequence(words)  # expect-error
    expect(items).is_subset_of(words)  # expect-error


def arguments_keep_their_own_types(items: list[int]) -> None:
    expect(items).has_length("3")  # expect-error
    expect(items).has_length_greater_than(None)  # expect-error
    expect(items).equals_approximately([1.0], tol="wide")  # expect-error
    expect(items).all_are_instance_of(3)  # expect-error: a type, not an instance


def because_is_keyword_only(items: list[int]) -> None:
    expect(items).is_empty("a reason")  # expect-error: `because` is keyword-only


def predicates_receive_the_element(items: list[int]) -> None:
    expect(items).only_contains(lambda value: value.upper())  # expect-error: not a str
    expect(items).is_sorted(key=complex)  # expect-error: complex is not orderable


def found_is_not_a_subject(items: list[int]) -> None:
    """`.and_` or `.which` is required; `Found` carries no assertions of its own."""
    expect(items).contains_single().is_empty()  # expect-error
    expect(items).has_element_at(0, 1).contains(1)  # expect-error


def found_continuations_keep_their_types(items: list[int]) -> None:
    assert_type(expect(items).contains_single(), Found[SequenceExpect[str], str])  # expect-error
    assert_type(expect(items).contains_single().which, SequenceExpect[int])  # expect-error
    assert_type(expect(items).has_element_at(0, 1).subject, str)  # expect-error


def wildcard_matching_is_for_strings(items: list[int], words: list[str]) -> None:
    expect(items).contains_match("a*")  # expect-error: the elements are not strings
    expect(items).does_not_contain_match("a*")  # expect-error
    expect(words).contains_match(3)  # expect-error: the pattern is a string
    assert_type(expect(words).contains_match("a*"), SequenceExpect[int])  # expect-error


class Lines(SequenceExpect[str]):
    """A subclass, to pin the half of `contains_match` that is easy to lose."""

    __slots__ = ()


def the_string_only_pair_does_not_widen_a_subclass(lines: list[str]) -> None:
    """It would be sound to hand back `SequenceExpect[str]` here, and it is wrong.

    The bound type variable exists precisely so the caller keeps the subject it
    started with; a return widened to the bound is the regression this line
    catches.
    """
    assert_type(Lines(lines).contains_match("a*"), SequenceExpect[str])  # expect-error
