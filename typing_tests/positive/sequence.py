"""The sequence subject's typed surface.

Four claims are pinned here.

*The element type survives* ``expect()``, so ``contains`` and its neighbours are
checked against it rather than against ``object``.

*Chaining preserves the concrete subject*, a user's own subclass included -- that
is what makes the extension model worth anything.

*The two assertions that find a value* hand back a ``Found``, whose ``.and_``
returns to the sequence and whose ``.which`` descends into the element.

*The string-only assertions stay string-only* -- and still hand back the subject
they were called on, subclass included: ``contains_match`` carries its constraint
in a bound type variable rather than a plain ``self`` annotation.
"""

from collections.abc import Sequence
from typing import Self, assert_type

from lovely_assertions import Expect, Found, SequenceExpect, custom_assertion, expect


# ---------------------------------------------------------------------------
# The element type survives, and every assertion returns the subject
# ---------------------------------------------------------------------------
def assertions_return_the_specialised_subject(items: list[int]) -> None:
    assert_type(expect(items).is_empty(), SequenceExpect[int])
    assert_type(expect(items).has_length(3), SequenceExpect[int])
    assert_type(expect(items).contains(2), SequenceExpect[int])
    assert_type(expect(items).is_sorted(), SequenceExpect[int])
    assert_type(expect(items).is_not_empty().and_.contains(2), SequenceExpect[int])
    assert_type(expect(items).subject, Sequence[int])


def a_tuple_is_a_sequence_too(pairs: tuple[str, ...]) -> None:
    assert_type(expect(pairs).contains("a"), SequenceExpect[str])
    assert_type(expect(pairs).subject, Sequence[str])


def cross_collection_arguments(items: list[int], rows: dict[str, int]) -> None:
    """Comparisons take what they actually need, not always a ``Sequence``."""
    assert_type(expect(items).equals_sequence((1, 2)), SequenceExpect[int])
    assert_type(expect(items).is_subset_of({1, 2}), SequenceExpect[int])
    assert_type(expect(items).intersects(frozenset({1})), SequenceExpect[int])
    assert_type(expect(items).has_same_length_as(rows), SequenceExpect[int])
    assert_type(expect(items).has_same_length_as("ab"), SequenceExpect[int])


# ---------------------------------------------------------------------------
# Found: `.and_` back to the sequence, `.which` into the element
# ---------------------------------------------------------------------------
def contains_single_finds_the_element(items: list[str]) -> None:
    found = expect(items).contains_single()
    assert_type(found, Found[SequenceExpect[str], str])
    assert_type(found.and_, SequenceExpect[str])
    assert_type(found.which, Expect[str])
    assert_type(found.subject, str)


def has_element_at_finds_the_element(items: list[str]) -> None:
    found = expect(items).has_element_at(0, "a")
    assert_type(found, Found[SequenceExpect[str], str])
    assert_type(found.which.is_equal_to("a"), Expect[str])
    assert_type(found.and_.has_length(1), SequenceExpect[str])


def a_nested_element_type_is_kept(rows: list[list[int]]) -> None:
    assert_type(expect(rows).contains_single().subject, list[int])
    assert_type(expect(rows).contains_single().which, Expect[list[int]])


# ---------------------------------------------------------------------------
# Callables: predicates, keys, inspections
# ---------------------------------------------------------------------------
def predicates_are_typed_to_the_element(words: list[str], items: list[int]) -> None:
    assert_type(expect(words).only_contains(str.isupper), SequenceExpect[str])
    assert_type(expect(items).only_contains(lambda value: value > 2), SequenceExpect[int])
    assert_type(expect(items).has_length_matching(lambda count: count > 2), SequenceExpect[int])
    assert_type(expect(items).satisfies_in_any_order(lambda value: value == 1), SequenceExpect[int])


def sort_keys_are_typed_to_the_element(words: list[str]) -> None:
    assert_type(expect(words).is_sorted(key=len), SequenceExpect[str])
    assert_type(expect(words).is_sorted_descending(key=str.casefold), SequenceExpect[str])
    assert_type(expect(words).is_not_sorted(key=len), SequenceExpect[str])
    assert_type(expect(words).is_not_sorted_descending(key=len), SequenceExpect[str])


def inspections_are_typed_to_the_element(items: list[int]) -> None:
    assert_type(
        expect(items).all_satisfy(lambda value: expect(value).is_equal_to(1)),
        SequenceExpect[int],
    )
    assert_type(
        expect(items).satisfies_respectively(lambda value: expect(value).is_equal_to(1)),
        SequenceExpect[int],
    )


# ---------------------------------------------------------------------------
# The string-only pair: constrained, and still self-typed
# ---------------------------------------------------------------------------
def contains_match_is_offered_only_on_strings(lines: list[str]) -> None:
    """``Self`` cannot be written next to an explicit ``self`` annotation.

    Both checkers reject that combination, so the constraint is carried by a type
    variable *bound* to ``SequenceExpect[str]``. It buys back what a plain
    ``self: SequenceExpect[str]`` would have cost: the return type is whatever
    the caller actually had, not a widening to the bound.
    """
    assert_type(expect(lines).contains_match("a*"), SequenceExpect[str])
    assert_type(expect(lines).does_not_contain_match("a*"), SequenceExpect[str])
    assert_type(expect(lines).contains_match("a*").and_.has_length(1), SequenceExpect[str])
    assert_type(expect(lines).contains_match("a*").subject, Sequence[str])


# ---------------------------------------------------------------------------
# Extension subjects get the same treatment
# ---------------------------------------------------------------------------
class LogExpect(SequenceExpect[str]):
    __slots__ = ()

    @custom_assertion
    def has_no_warnings(self, *, because: str = "") -> Self:
        for line in self._subject:
            if line.startswith("WARN"):
                return self._fail(f"to have no warnings, but found {line!r}", because)
        return self


def a_subclass_keeps_its_identity_across_a_chain(lines: list[str]) -> None:
    subject = LogExpect(lines)
    assert_type(subject.is_not_empty(), LogExpect)
    assert_type(subject.has_no_warnings(), LogExpect)
    assert_type(subject.is_not_empty().and_.has_no_warnings(), LogExpect)
    assert_type(subject.contains_single(), Found[LogExpect, str])
    assert_type(subject.contains_single().and_, LogExpect)
    assert_type(subject.contains_match("a*"), LogExpect)
    assert_type(subject.does_not_contain_match("a*").and_.has_no_warnings(), LogExpect)
