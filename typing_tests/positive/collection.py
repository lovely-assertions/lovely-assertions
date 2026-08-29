"""The collection subject's typed surface.

Five claims are pinned here.

*The element type survives*, so ``contains`` and its neighbours are checked
against it rather than against ``object`` -- on a ``set``, a ``frozenset`` or a
dict view, none of which is a ``Sequence``.

*A sequence is a collection.* ``SequenceExpect[E]`` derives from
``CollectionExpect[E]``, so anything written against the order-free surface
accepts a list, and the inherited assertions hand back the *sequence* subject
rather than widening to the base. That is what makes the split a refinement
rather than two libraries.

*The set algebra returns the subject*, and takes any collection as its argument:
comparing a set against a list or against a mapping's keys is a fair question.

*The assertion that finds a value* hands back a ``Found``, whose ``.and_``
returns to the collection and whose ``.which`` descends into the element.

*The string-only pair stays string-only* -- and still hands back the subject it
was called on, subclass included: ``contains_match`` carries its constraint in a
bound type variable rather than a plain ``self`` annotation.

The subject is constructed rather than obtained from ``expect()``: the dispatch
that hands an unordered collection to this subject is declared centrally, and
what this file is about is the class's own surface.
"""

from collections.abc import Collection, Sequence
from typing import Self, assert_type

from lovely_assertions import Expect, Found, SequenceExpect, custom_assertion, expect

# Imported from the module that declares it, as the neighbouring subject files
# do; the package root re-exports the same class.
from lovely_assertions._collection import CollectionExpect


# ---------------------------------------------------------------------------
# The element type survives, and every assertion returns the subject
# ---------------------------------------------------------------------------
def assertions_return_the_specialised_subject(tags: set[int]) -> None:
    subject = CollectionExpect[int](tags)
    assert_type(subject.is_empty(), CollectionExpect[int])
    assert_type(subject.has_length(3), CollectionExpect[int])
    assert_type(subject.contains(2), CollectionExpect[int])
    assert_type(subject.is_not_empty().and_.contains(2), CollectionExpect[int])
    assert_type(subject.subject, Collection[int])


def every_unordered_built_in_reaches_the_subject(rows: dict[str, int]) -> None:
    """The hole this subject fills: none of these is a ``Sequence``."""
    assert_type(CollectionExpect[str](rows.keys()).contains("a"), CollectionExpect[str])
    assert_type(CollectionExpect[int](rows.values()).contains(1), CollectionExpect[int])
    assert_type(
        CollectionExpect[tuple[str, int]](rows.items()).contains(("a", 1)),
        CollectionExpect[tuple[str, int]],
    )
    assert_type(CollectionExpect[bytes](frozenset({b"a"})).is_not_empty(), CollectionExpect[bytes])


def the_set_algebra_takes_any_collection(tags: set[int], rows: dict[int, str]) -> None:
    assert_type(CollectionExpect[int](tags).is_subset_of([1, 2]), CollectionExpect[int])
    assert_type(CollectionExpect[int](tags).is_superset_of(frozenset({1})), CollectionExpect[int])
    assert_type(CollectionExpect[int](tags).is_proper_subset_of((1, 2)), CollectionExpect[int])
    assert_type(CollectionExpect[int](tags).is_proper_superset_of({1}), CollectionExpect[int])
    assert_type(CollectionExpect[int](tags).is_disjoint_from(rows.keys()), CollectionExpect[int])
    assert_type(CollectionExpect[int](tags).contains_only(1, 2), CollectionExpect[int])
    assert_type(CollectionExpect[int](tags).contains_none_of(3), CollectionExpect[int])
    assert_type(CollectionExpect[int](tags).has_same_length_as(rows), CollectionExpect[int])


# ---------------------------------------------------------------------------
# A sequence is a collection: the split is a refinement
# ---------------------------------------------------------------------------
def count_them(items: CollectionExpect[int]) -> int:
    """Anything written against the order-free surface accepts either subject."""
    return len(items.is_not_empty().subject)


def a_sequence_subject_is_accepted_where_a_collection_is_wanted(items: list[int]) -> None:
    assert_type(count_them(expect(items)), int)
    assert_type(count_them(CollectionExpect[int]({1, 2})), int)


def the_inherited_half_keeps_the_sequence_subject(items: list[int]) -> None:
    """Inherited, not widened: ``.and_`` after ``contains`` still offers ``is_sorted``."""
    assert_type(expect(items).contains(2), SequenceExpect[int])
    assert_type(expect(items).is_subset_of({1}), SequenceExpect[int])
    assert_type(expect(items).contains_only(1, 2), SequenceExpect[int])
    assert_type(expect(items).contains(2).and_.is_sorted(), SequenceExpect[int])
    assert_type(expect(items).subject, Sequence[int])


# ---------------------------------------------------------------------------
# Found: `.and_` back to the collection, `.which` into the element
# ---------------------------------------------------------------------------
def contains_single_finds_the_element(tags: set[str]) -> None:
    found = CollectionExpect[str](tags).contains_single()
    assert_type(found, Found[CollectionExpect[str], str])
    assert_type(found.and_, CollectionExpect[str])
    assert_type(found.which, Expect[str])
    assert_type(found.subject, str)


def a_nested_element_type_is_kept(rows: dict[str, list[int]]) -> None:
    subject = CollectionExpect[list[int]](rows.values())
    assert_type(subject.contains_single().subject, list[int])
    assert_type(subject.contains_single().which, Expect[list[int]])


def finding_by_predicate_continues_on_the_element(rows: set[str]) -> None:
    """``contains_matching(p).which`` is the pattern the assertion exists for."""
    subject = CollectionExpect[str](rows)
    found = subject.contains_matching(str.isupper)
    assert_type(found, Found[CollectionExpect[str], str])
    assert_type(found.and_, CollectionExpect[str])
    assert_type(found.which, Expect[str])
    assert_type(found.subject, str)
    assert_type(subject.contains_single_matching(str.isupper), Found[CollectionExpect[str], str])
    assert_type(subject.does_not_contain_matching(str.isupper), CollectionExpect[str])


def the_multi_item_family_returns_the_subject(tags: set[int]) -> None:
    subject = CollectionExpect[int](tags)
    assert_type(subject.contains_all(1, 2), CollectionExpect[int])
    assert_type(subject.does_not_contain_all(1, 2), CollectionExpect[int])
    assert_type(subject.contains_any(1, 2), CollectionExpect[int])
    assert_type(subject.does_not_contain_items_of_type(str), CollectionExpect[int])


def the_key_parameters_are_typed_to_the_element(rows: dict[str, list[int]]) -> None:
    """``key`` sees the element, and its result is free -- it is only ever compared."""
    subject = CollectionExpect[list[int]](rows.values())
    assert_type(subject.has_unique_items(key=len), CollectionExpect[list[int]])
    assert_type(subject.contains_no_duplicates(key=len), CollectionExpect[list[int]])
    assert_type(subject.does_not_contain_none(key=lambda row: row[0]), CollectionExpect[list[int]])


# ---------------------------------------------------------------------------
# Callables: predicates and inspections
# ---------------------------------------------------------------------------
def predicates_are_typed_to_the_element(words: set[str], tags: set[int]) -> None:
    assert_type(CollectionExpect[str](words).only_contains(str.isupper), CollectionExpect[str])
    assert_type(
        CollectionExpect[int](tags).only_contains(lambda value: value > 2), CollectionExpect[int]
    )
    assert_type(
        CollectionExpect[int](tags).has_length_matching(lambda count: count > 2),
        CollectionExpect[int],
    )
    assert_type(
        CollectionExpect[int](tags).satisfies_in_any_order(lambda value: value == 1),
        CollectionExpect[int],
    )


def inspections_are_typed_to_the_element(tags: set[int]) -> None:
    assert_type(
        CollectionExpect[int](tags).all_satisfy(lambda value: expect(value).is_equal_to(1)),
        CollectionExpect[int],
    )


# ---------------------------------------------------------------------------
# The string-only pair: constrained, and still self-typed
# ---------------------------------------------------------------------------
def contains_match_is_offered_only_on_strings(lines: set[str], rows: list[str]) -> None:
    """The bound admits both subjects, and neither is widened to it.

    ``Self`` cannot be written next to an explicit ``self`` annotation -- both
    checkers reject that -- so the constraint is a type variable *bound* to
    ``CollectionExpect[str]``. A ``SequenceExpect[str]`` satisfies that bound and
    still comes back as itself.
    """
    assert_type(CollectionExpect[str](lines).contains_match("a*"), CollectionExpect[str])
    assert_type(CollectionExpect[str](lines).does_not_contain_match("a*"), CollectionExpect[str])
    assert_type(expect(rows).contains_match("a*"), SequenceExpect[str])
    assert_type(expect(rows).contains_match("a*").and_.is_sorted(), SequenceExpect[str])


# ---------------------------------------------------------------------------
# extracting: the element type is inferred, and the *subject* depends on the source
# ---------------------------------------------------------------------------
def extracting_infers_the_element_type_from_the_selector(rows: set[str]) -> None:
    """The whole argument for the callable form: ``R`` comes from the function.

    ``extracting("name")`` -- assertpy's spelling -- could only ever produce
    ``Any``, and every assertion downstream of it would be unchecked.
    """
    assert_type(CollectionExpect[str](rows).extracting(len), CollectionExpect[int])
    assert_type(
        CollectionExpect[str](rows).extracting(lambda tag: tag.encode()), CollectionExpect[bytes]
    )
    assert_type(CollectionExpect[str](rows).extracting(len).extracting(str), CollectionExpect[str])


def extracting_keeps_the_order_free_subject_order_free(tags: set[int]) -> None:
    """The trap the return type closes.

    Extraction materialises a list, so handing back a ``SequenceExpect`` would
    type-check -- and would let ``is_sorted`` be asked of a ``set``'s iteration
    order. ``collection_negative.py`` holds the line that proves it cannot be.
    """
    assert_type(CollectionExpect[int](tags).extracting(str), CollectionExpect[str])
    assert_type(CollectionExpect[int](tags).extracting(str).contains("1"), CollectionExpect[str])


def extracting_from_a_sequence_re_earns_the_ordered_catalogue(rows: list[str]) -> None:
    """The override, and the reason it is sound: the source has an order to preserve."""
    assert_type(expect(rows).extracting(len), SequenceExpect[int])
    assert_type(expect(rows).extracting(len).is_sorted(), SequenceExpect[int])
    assert_type(expect(rows).extracting(len).has_element_at(0, 3), Found[SequenceExpect[int], int])


# ---------------------------------------------------------------------------
# Extension subjects get the same treatment
# ---------------------------------------------------------------------------
class TagsExpect(CollectionExpect[str]):
    """A custom subject pinned to an element type: the ordinary shape of an extension."""

    __slots__ = ()

    @custom_assertion
    def has_no_internal_tags(self, *, because: str = "") -> Self:
        for tag in self._subject:
            if tag.startswith("_"):
                return self._fail(f"to have no internal tags, but found {tag!r}", because)
        return self


class BagExpect[E](CollectionExpect[E, Collection[E]]):
    """A *generic* custom subject.

    Both parameters are spelled out on purpose: CPython does not substitute a
    PEP 696 default that refers to another type parameter, so
    ``class BagExpect[E](CollectionExpect[E])`` type-checks and then raises
    ``TypeError`` when the class is created. The concrete form above is
    unaffected.
    """

    __slots__ = ()


def a_subclass_keeps_its_identity_across_a_chain(tags: set[str]) -> None:
    subject = TagsExpect(tags)
    assert_type(subject.is_not_empty(), TagsExpect)
    assert_type(subject.has_no_internal_tags(), TagsExpect)
    assert_type(subject.is_not_empty().and_.has_no_internal_tags(), TagsExpect)
    assert_type(subject.contains_single(), Found[TagsExpect, str])
    assert_type(subject.contains_single().and_, TagsExpect)
    assert_type(subject.contains_match("a*"), TagsExpect)
    assert_type(subject.is_superset_of({"a"}).and_.has_no_internal_tags(), TagsExpect)
    assert_type(subject.contains_all("a"), TagsExpect)
    assert_type(subject.contains_matching(str.isupper), Found[TagsExpect, str])
    assert_type(subject.has_unique_items(key=len).and_.has_no_internal_tags(), TagsExpect)
    # `extracting` is the one that cannot: the element type has changed, so the
    # subclass no longer describes what is in hand.
    assert_type(subject.extracting(len), CollectionExpect[int])


def a_generic_subclass_keeps_its_element_type(numbers: set[int]) -> None:
    assert_type(BagExpect(numbers).contains(1), BagExpect[int])
    assert_type(BagExpect(numbers).subject, Collection[int])
