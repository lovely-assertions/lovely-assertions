"""The order-free catalogue: ``CollectionExpect[E]``, the unordered half.

Three things are being tested here.

*Behaviour on a subject that really has no order.* Every assertion is exercised
against a ``set``, a ``frozenset`` or a dict view -- not against a list that
happens to be typed loosely. An assertion that quietly needed ``subject[0]``
passes on a list and raises ``TypeError`` on a set, so the only way to know the
split is real is to run it on the unordered side.

*Messages, verbatim, with no positional language.* An item of a set is not *at*
index 3, so the inherited half must report without one.
``test_no_failure_message_claims_a_position`` walks the whole catalogue and
enforces that.

*The set algebra* -- superset, proper subset and superset, disjointness,
``contains_only`` and ``contains_none_of`` -- including the edges that decide
what those words mean here: repeats are ignored, an empty collection is a subset
of everything, and "only" is exact in both directions.

Two conventions worth stating.

**The subject is built explicitly.** ``expect({1, 2})`` reaching this subject is
dispatch, which is wired centrally; constructing the subject directly is the
route a user-written subject takes, and it is what makes subject-name recovery
name the variable rather than the expression that produced it. ``Bag`` below is
that subject, generic so that one class covers every element type this file needs.

**Rendered sets in asserted messages hold integers, never several strings.**
String hashes are randomised per process, so ``{"a", "b"}`` iterates either way
round and a message asserted against it would fail one run in two. Integers hash
to themselves; where strings are unavoidable the subject is a dict view, which
keeps insertion order.
"""

import inspect
import time
from collections.abc import Callable, Collection
from typing import Any, Final, cast

import pytest
from benchmarks import blocks_allocated

from _happy_calls import declared_by_the_subject
from lovely_assertions import (
    AssertionFailure,
    Found,
    SequenceExpect,
    expect,
    soft_assertions,
)
from lovely_assertions._collection import CollectionExpect
from lovely_assertions._collection._hashing import (
    _HASHING_PAYS_FROM,  # pyright: ignore[reportPrivateUsage]
    _LONGEST_CONTAINER_PER_LOOKUP,  # pyright: ignore[reportPrivateUsage]
    _REPEATED_LOOKUPS_FROM,  # pyright: ignore[reportPrivateUsage]
    searchable,
)
from lovely_assertions._formatting import formatting
from lovely_assertions._occurrence import (
    Occurrence,
    at_least,
    at_most,
    exactly,
    less_than,
    more_than,
    once,
    twice,
)


class Bag[E](CollectionExpect[E, Collection[E]]):
    """The subject these tests build.

    A subclass rather than ``CollectionExpect`` itself, for one reason: subject
    names. ``resolve_subject_name`` recognises a call to a name that resolves to
    an ``Expect`` subclass, so ``Bag(tags)`` names ``tags`` in the message, while
    ``Bag[str](tags)`` -- a subscript, not a name -- falls back to "the value".
    It is generic so one class covers every element type these tests need, and it
    declares nothing of its own, so every message asserted below is the one
    ``CollectionExpect`` produces.

    Both type parameters are spelled out because a *generic* subclass has to:
    CPython does not substitute a PEP 696 default that refers to another type
    parameter, so ``class Bag[E](CollectionExpect[E])`` raises ``TypeError`` at
    class-creation time. A subclass pinned to a concrete element type --
    ``class TagsExpect(CollectionExpect[str])``, the shape a subject written for
    one element type takes -- is unaffected.
    """

    __slots__ = ()


class Animal:
    __slots__ = ()

    def __repr__(self) -> str:
        return "Animal()"


class Dog(Animal):
    __slots__ = ()

    def __repr__(self) -> str:
        return "Dog()"


class Weight:
    """Equal by value, never by identity -- the distinction ``all_equal_to`` makes.

    Small integers are interned, so a suite that only ever asserts about them
    cannot tell ``==`` from ``is``. This type can: two ``Weight(5)`` are equal and
    are not the same object.
    """

    __slots__ = ("grams",)

    def __init__(self, grams: int, /) -> None:
        self.grams = grams

    def __repr__(self) -> str:
        return "Weight(" + str(self.grams) + ")"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Weight) and other.grams == self.grams

    def __hash__(self) -> int:
        return hash(self.grams)


class Row:
    """A record with fields worth extracting -- the subject ``key=`` exists for.

    Hashable by identity, which is the point: two rows carrying the same id are
    different objects, so uniqueness *of the row* would report nothing and
    uniqueness of ``row.id`` is the question being asked.
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


#: An empty set with a known element type. A bare ``set()`` leaves the element
#: type unsolved, which is exactly what the strict typing surface should reject.
EMPTY: set[int] = set()


def missing_collection() -> Bag[int]:
    """A subject whose value is ``None`` -- a cast is how one really gets here."""
    return Bag(cast("Collection[int]", None))


def passes(assertion: "Callable[..., object]", /, *arguments: object) -> bool:
    """Whether an assertion passed, for comparing two spellings of one question.

    Takes the bound method and its arguments rather than a thunk: a ``lambda``
    written inside a loop captures the loop variable, which is the classic way a
    table-driven comparison ends up testing the last row four times.
    """
    try:
        assertion(*arguments)
    except AssertionFailure:
        return False
    return True


# ---------------------------------------------------------------------------
# The subject reaches the collections that have no sequence to fall back on
# ---------------------------------------------------------------------------
def test_the_subject_covers_sets_frozensets_and_dict_views() -> None:
    """Every unordered built-in is a subject here: set, frozenset, all three dict views.

    These are the collections with no sequence to fall back on, which is the hole
    this subject exists to fill.
    """
    rows = {"a": 1, "b": 2}
    Bag({1, 2}).contains(1).and_.has_length(2)
    Bag(frozenset({1, 2})).contains(2).and_.is_not_empty()
    Bag(rows.keys()).contains("a").and_.has_length(2)
    Bag(rows.values()).contains(2).and_.does_not_contain(9)
    Bag(rows.items()).contains(("a", 1))


def test_a_dict_view_stays_a_live_view() -> None:
    """Nothing here copies the subject, so the assertion sees the mapping as it is."""
    rows = {"a": 1}
    subject = Bag(rows.keys())
    rows["b"] = 2
    subject.has_length(2).and_.contains("b")


# ---------------------------------------------------------------------------
# Emptiness
# ---------------------------------------------------------------------------
def test_is_empty_passes_and_chains() -> None:
    subject = Bag(EMPTY)
    assert subject.is_empty() is subject


def test_is_empty_shows_the_collection() -> None:
    items = {1, 2, 3}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).is_empty()
    assert str(caught.value) == "Expected items to be empty, but was {1, 2, 3}."


def test_is_not_empty() -> None:
    Bag({1}).is_not_empty()
    items: set[int] = set()
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).is_not_empty()
    assert str(caught.value) == "Expected items not to be empty, but it was."


def test_is_none_or_empty_accepts_both_cases() -> None:
    Bag(EMPTY).is_none_or_empty()
    subject = missing_collection()
    assert subject.is_none_or_empty() is subject


def test_is_not_none_or_empty_reports_which_case_it_was() -> None:
    """The subject is built inside the statement, so the name falls back cleanly."""
    Bag({1}).is_not_none_or_empty()
    with pytest.raises(AssertionFailure) as caught:
        missing_collection().is_not_none_or_empty()
    assert str(caught.value) == "Expected the value not to be None or empty, but was None."

    items: set[int] = set()
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).is_not_none_or_empty()
    assert str(caught.value) == "Expected items not to be None or empty, but was set()."


# ---------------------------------------------------------------------------
# Length
# ---------------------------------------------------------------------------
def test_has_length_reports_both_counts_and_the_collection() -> None:
    Bag({1, 2}).has_length(2)
    items = {1, 2, 3}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).has_length(5)
    assert str(caught.value) == "Expected items to have length 5, but had 3: {1, 2, 3}."


def test_the_length_family_reads_the_same_as_it_does_on_a_sequence() -> None:
    items = {1, 2}
    Bag(items).has_length_greater_than(1).and_.has_length_greater_than_or_equal_to(2)
    Bag(items).has_length_less_than(3).and_.has_length_less_than_or_equal_to(2)
    Bag(items).does_not_have_length(3).and_.has_length_matching(lambda count: count == 2)

    with pytest.raises(AssertionFailure) as caught:
        Bag(items).has_length_greater_than(3)
    assert str(caught.value) == "Expected items to have more than 3 items, but had 2: {1, 2}."

    with pytest.raises(AssertionFailure) as caught:
        Bag(items).has_length_less_than_or_equal_to(1)
    assert str(caught.value) == "Expected items to have at most 1 item, but had 2: {1, 2}."


def test_the_length_comparisons_are_strict_at_their_boundary() -> None:
    """More than 2 is not at least 2, and the message counts in the singular.

    Both halves are pinned because a suite that only ever asks for a count well
    clear of the real one proves neither: it cannot tell ``>`` from ``>=``, and
    it never renders "1 item", so it cannot tell ``count_of`` from a bare number
    with an "s" stuck on it.
    """
    items = {1, 2}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).has_length_greater_than(2)
    assert str(caught.value) == "Expected items to have more than 2 items, but had 2: {1, 2}."

    with pytest.raises(AssertionFailure) as caught:
        Bag(items).has_length_greater_than_or_equal_to(3)
    assert str(caught.value) == "Expected items to have at least 3 items, but had 2: {1, 2}."

    with pytest.raises(AssertionFailure) as caught:
        Bag(items).has_length_less_than(2)
    assert str(caught.value) == "Expected items to have fewer than 2 items, but had 2: {1, 2}."

    single = {7}
    with pytest.raises(AssertionFailure) as caught:
        Bag(single).has_length_greater_than(1)
    assert str(caught.value) == "Expected single to have more than 1 item, but had 1: {7}."

    none_yet: set[int] = set()
    with pytest.raises(AssertionFailure) as caught:
        Bag(none_yet).has_length_greater_than_or_equal_to(1)
    assert str(caught.value) == "Expected none_yet to have at least 1 item, but had 0: set()."

    with pytest.raises(AssertionFailure) as caught:
        Bag(single).has_length_less_than(1)
    assert str(caught.value) == "Expected single to have fewer than 1 item, but had 1: {7}."


def test_has_same_length_as_accepts_any_collection() -> None:
    rows = {"a": 1, "b": 2}
    Bag({1, 2}).has_same_length_as(rows)
    Bag({1, 2}).has_same_length_as([3, 4])
    items = {1, 2, 3}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).has_same_length_as((1, 2))
    assert str(caught.value) == (
        "Expected items to have the same length as (1, 2), but had 3 items against 2."
    )


def test_does_not_have_same_length_as() -> None:
    Bag({1, 2}).does_not_have_same_length_as({1})
    items = {1, 2}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).does_not_have_same_length_as([3, 4])
    assert str(caught.value) == (
        "Expected items not to have the same length as [3, 4], but both had 2 items."
    )


# ---------------------------------------------------------------------------
# Containment
# ---------------------------------------------------------------------------
def test_contains_shows_what_was_missing_and_the_collection() -> None:
    Bag({1, 2}).contains(2)
    items = {1, 2, 3}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).contains(9)
    assert str(caught.value) == "Expected items to contain 9, but was {1, 2, 3}."


def test_does_not_contain_cannot_and_does_not_claim_a_position() -> None:
    """The sequence subject says "at index 1" here; a set has no answer to that."""
    Bag({1, 2}).does_not_contain(9)
    items = {1, 2, 3}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).does_not_contain(2)
    assert str(caught.value) == "Expected items not to contain 2, but found it: {1, 2, 3}."


# ---------------------------------------------------------------------------
# Occurrences: how many items equal the one asked for
# ---------------------------------------------------------------------------
#: Two "ada" and one "bob". A ``dict`` view rather than a set, for two reasons: a
#: set cannot hold a repeat, so there would be nothing to count, and a view keeps
#: insertion order, so the rendered collection in an asserted message is stable.
VOTES: Final = {"first": "ada", "second": "ada", "third": "bob"}

#: One NaN, reused. Two NaNs are two values (they are equal to nothing, each
#: other included), and the difference is the whole of the identity-first rule.
NAN: Final = float("nan")

#: A deliberately untyped door to the subject, so that a call which is *meant* to
#: be wrong needs no suppression -- one spelling for mypy and another for pyright
#: is how a test file fills up with noise. ``tests/test_formatting.py`` does the
#: same.
UNTYPED: Any = Bag


class Between:
    """A user's own occurrence constraint: ``Occurrence`` is a structural protocol.

    Two methods and no base class is the whole of what it asks for.
    Annotated as an ``Occurrence`` where it is used, so both checkers verify the
    structural match at the call site rather than at runtime -- which is the only
    place it can be verified, the protocol not being ``runtime_checkable``.
    """

    __slots__ = ("_high", "_low")

    def __init__(self, low: int, high: int, /) -> None:
        self._low = low
        self._high = high

    def allows(self, count: int, /) -> bool:
        return self._low <= count <= self._high

    def describe(self) -> str:
        return "between " + str(self._low) + " and " + str(self._high) + " times"


def held(assertion: "Callable[..., object]", item: object, constraint: Occurrence, /) -> bool:
    """Whether an occurrence-constrained assertion held.

    ``passes`` above cannot express this: it forwards positional arguments, and
    ``occurrences`` is keyword-only on purpose.
    """
    try:
        assertion(item, occurrences=constraint)
    except AssertionFailure:
        return False
    return True


#: Each constraint against a count of **two**, with the answer it owes. Named
#: rather than inlined so the two tables below -- the assertion and its exact
#: complement -- cannot drift apart.
COUNTED_TWICE: Final = [
    pytest.param(exactly(2), True, id="exactly-2"),
    pytest.param(exactly(3), False, id="exactly-3"),
    pytest.param(at_least(2), True, id="at_least-2"),
    pytest.param(at_least(3), False, id="at_least-3"),
    pytest.param(at_most(2), True, id="at_most-2"),
    pytest.param(at_most(1), False, id="at_most-1"),
    pytest.param(more_than(1), True, id="more_than-1"),
    pytest.param(more_than(2), False, id="more_than-2"),
    pytest.param(less_than(3), True, id="less_than-3"),
    pytest.param(less_than(2), False, id="less_than-2"),
    pytest.param(once, False, id="once"),
    pytest.param(twice, True, id="twice"),
]


def test_no_constraint_leaves_the_membership_test_and_its_messages_alone() -> None:
    """An unconstrained call is the default branch: same membership test, same words.

    ``occurrences=`` puts a second branch behind these two names, and this is
    what fails if an unconstrained call ever starts routing through it -- where
    the verdict would still be right and the wording, and the cost, would not.
    """
    items = {1, 2, 3}
    Bag(items).contains(2).and_.does_not_contain(9)
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).contains(9)
    assert str(caught.value) == "Expected items to contain 9, but was {1, 2, 3}."
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).does_not_contain(2)
    assert str(caught.value) == "Expected items not to contain 2, but found it: {1, 2, 3}."


def test_contains_counts_the_items_that_equal_the_one_asked_for() -> None:
    subject = Bag(VOTES.values())
    assert subject.contains("ada", occurrences=twice) is subject
    subject.contains("bob", occurrences=once)
    subject.contains("zoe", occurrences=exactly(0))


def test_the_constrained_failure_names_the_constraint_and_the_count() -> None:
    """The sentence the constraint was designed to land in (``_occurrence``)."""
    votes = VOTES.values()
    with pytest.raises(AssertionFailure) as caught:
        Bag(votes).contains("ada", occurrences=exactly(3))
    assert str(caught.value) == (
        "Expected votes to contain 'ada' exactly 3 times, but found 2: ['ada', 'ada', 'bob']."
    )


def test_the_constrained_negative_names_the_constraint_and_the_count_too() -> None:
    votes = VOTES.values()
    with pytest.raises(AssertionFailure) as caught:
        Bag(votes).does_not_contain("ada", occurrences=twice)
    assert str(caught.value) == (
        "Expected votes not to contain 'ada' exactly twice, but found 2: ['ada', 'ada', 'bob']."
    )


@pytest.mark.parametrize(("constraint", "holds"), COUNTED_TWICE)
def test_every_shipped_constraint_is_asked_about_the_count(
    constraint: Occurrence, holds: bool
) -> None:
    assert held(Bag(VOTES.values()).contains, "ada", constraint) is holds


@pytest.mark.parametrize(("constraint", "holds"), COUNTED_TWICE)
def test_does_not_contain_negates_the_constraint_not_the_containment(
    constraint: Occurrence, holds: bool
) -> None:
    """The reading that makes the pair worth having.

    ``does_not_contain(x, occurrences=exactly(3))`` passes on two, on four and on
    none -- it says "not three times", not "not there". Anything else would make
    the two spellings of one constraint mean different things.
    """
    assert held(Bag(VOTES.values()).does_not_contain, "ada", constraint) is not holds


def test_a_value_equal_to_several_distinct_items_counts_each_of_them() -> None:
    """The count is of *items*, not of one object's appearances.

    ``1``, ``1.0`` and ``True`` are three distinct items and all three equal
    ``1``, so the count is three. ``list.count`` reads it the same way, and any
    other reading would need a comparison that is not ``==``.
    """
    numbers = {"int": 1, "float": 1.0, "bool": True}.values()
    Bag(numbers).contains(1, occurrences=exactly(3))
    with pytest.raises(AssertionFailure) as caught:
        Bag(numbers).contains(1, occurrences=once)
    assert str(caught.value) == (
        "Expected numbers to contain 1 exactly once, but found 3: [1, 1.0, True]."
    )


def test_a_nan_is_counted_where_it_actually_is() -> None:
    """``in`` tries identity before equality, and so does the count.

    ``_mapping`` writes this rule out at each of its sites; the count follows it
    for the same reason. Equality alone would report zero occurrences of a value
    the collection demonstrably holds -- and would have ``contains(nan)`` and
    ``contains(nan, occurrences=more_than(0))`` disagree on the same collection.
    """
    same = {"a": NAN, "b": NAN}.values()
    other = {"a": float("nan")}.values()
    assert NAN in same  # the rule being followed, straight from Python
    assert NAN not in other

    Bag(same).contains(NAN, occurrences=twice)
    Bag(same).contains(NAN)
    Bag(other).contains(NAN, occurrences=exactly(0))
    Bag(other).does_not_contain(NAN)


def test_the_count_and_the_plain_membership_test_never_disagree() -> None:
    """Two spellings of one question, so they must not have two answers."""
    rows: dict[str, object] = {"a": 1, "b": NAN, "c": Weight(5)}
    values = rows.values()
    for item in (1, NAN, Weight(5), float("nan"), 9, Weight(6)):
        subject = Bag(values)
        assert passes(subject.contains, item) is held(subject.contains, item, more_than(0)), item


def test_a_user_written_constraint_is_accepted_and_read_back() -> None:
    """Two methods and no base class, which is what a ``Protocol`` promises."""
    constraint: Occurrence = Between(1, 2)
    votes = VOTES.values()
    Bag(votes).contains("ada", occurrences=constraint)
    with pytest.raises(AssertionFailure) as caught:
        Bag(votes).contains("bob", occurrences=Between(2, 3))
    assert str(caught.value) == (
        "Expected votes to contain 'bob' between 2 and 3 times, but found 1: ['ada', 'ada', 'bob']."
    )


def test_the_constraint_is_keyword_only() -> None:
    """Positionally it would read as a second item to look for."""
    with pytest.raises(TypeError):
        UNTYPED({1}).contains(1, once)
    with pytest.raises(TypeError):
        UNTYPED({1}).does_not_contain(9, once)


def test_because_reaches_the_constrained_forms() -> None:
    """The ``because`` table below calls the unconstrained branch; this is the other."""
    votes = VOTES.values()
    with pytest.raises(AssertionFailure, match="because R"):
        Bag(votes).contains("ada", occurrences=once, because="R")
    with pytest.raises(AssertionFailure, match="because R"):
        Bag(votes).does_not_contain("ada", occurrences=twice, because="R")


def test_a_constrained_failure_is_collected_by_a_soft_scope() -> None:
    votes = VOTES.values()
    with soft_assertions() as scope:
        Bag(votes).contains("ada", occurrences=once).and_.does_not_contain("bob", occurrences=once)
        messages = scope.discard()
    assert [message.partition(",")[0] for message in messages] == [
        "Expected votes to contain 'ada' exactly once",
        "Expected votes not to contain 'bob' exactly once",
    ]


def test_a_constrained_message_claims_no_position() -> None:
    """The rule the whole class exists for, applied to the counted branch too."""
    votes = VOTES.values()
    calls: list[Callable[[], object]] = [
        lambda: Bag(votes).contains("ada", occurrences=once),
        lambda: Bag(votes).does_not_contain("ada", occurrences=twice),
    ]
    for call in calls:
        with pytest.raises(AssertionFailure) as caught:
            call()
        assert "index" not in str(caught.value)


def test_a_passing_constrained_assertion_allocates_nothing() -> None:
    """A passing assertion allocates nothing, the counted branch included.

    Counting is a loop rather than ``sum(1 for ...)`` precisely because the
    generator expression would be an allocation on every passing call.
    """
    baseline = blocks_allocated(lambda: None)
    subject = Bag(VOTES.values())
    assert blocks_allocated(lambda: subject.contains("ada", occurrences=twice)) <= baseline
    assert blocks_allocated(lambda: subject.does_not_contain("ada", occurrences=once)) <= baseline


def test_contains_single_continues_on_the_only_item() -> None:
    found = Bag({42}).contains_single()
    assert isinstance(found, Found)
    assert found.subject == 42
    assert found.which.is_equal_to(42).subject == 42
    assert found.and_.has_length(1).subject == {42}


def test_contains_single_reports_the_count() -> None:
    items = {1, 2, 3}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).contains_single()
    assert str(caught.value) == "Expected items to contain a single item, but had 3: {1, 2, 3}."


def test_only_contains_lists_every_item_that_failed() -> None:
    def is_even(value: int) -> bool:
        return value % 2 == 0

    Bag({2, 4}).only_contains(is_even)
    items = {1, 2, 3}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).only_contains(is_even)
    assert str(caught.value) == (
        "Expected items to contain only items matching is_even, but [1, 3] did not."
    )


# ---------------------------------------------------------------------------
# Find by predicate, with a continuation
# ---------------------------------------------------------------------------
def is_even(value: int) -> bool:
    """A named predicate, so the message can be asserted against its name."""
    return value % 2 == 0


def test_contains_matching_continues_on_the_item_it_found() -> None:
    """The point of the assertion: find the row, then assert on it, in one statement."""
    subject = Bag({2, 3})
    found = subject.contains_matching(is_even)
    assert isinstance(found, Found)
    assert found.subject == 2
    assert found.and_ is subject
    found.which.is_equal_to(2)


def test_contains_matching_says_how_many_it_checked_and_shows_a_sample() -> None:
    """ "no item matched" is useless on a long collection; this is the whole reason it exists."""
    numbers = frozenset(range(1, 500, 2))
    with pytest.raises(AssertionFailure) as caught:
        Bag(numbers).contains_matching(is_even)
    message = str(caught.value)
    assert message.startswith(
        "Expected numbers to contain an item matching is_even,"
        " but checked 250 items and none matched: [1, 3, 5, 7, 9, 11, 13, 15, 17, 19,"
    )
    assert message.endswith("... (240 more)].")


def test_contains_matching_reports_an_empty_collection_as_one() -> None:
    """ "checked 0 items" in front of ``set()`` reads like a bug in the library."""
    empty: set[int] = set()
    with pytest.raises(AssertionFailure) as caught:
        Bag(empty).contains_matching(is_even)
    assert str(caught.value) == (
        "Expected empty to contain an item matching is_even, but it was empty."
    )


def test_the_count_of_what_was_checked_is_a_sentence() -> None:
    """One item is "1 item", never "1 items".

    The plural is the common case, so the singular is the one that rots unwatched.
    """
    items = {1}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).contains_matching(is_even)
    assert str(caught.value) == (
        "Expected items to contain an item matching is_even,"
        " but checked 1 item and none matched: {1}."
    )


def test_an_anonymous_predicate_is_named_the_way_every_other_one_is() -> None:
    items = {1, 3}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).contains_matching(lambda value: value > 9)
    assert str(caught.value) == (
        "Expected items to contain an item matching the predicate,"
        " but checked 2 items and none matched: {1, 3}."
    )


def test_does_not_contain_matching_names_the_offender() -> None:
    subject = Bag({1, 3})
    assert subject.does_not_contain_matching(is_even) is subject
    items = {1, 2}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).does_not_contain_matching(is_even)
    assert str(caught.value) == (
        "Expected items not to contain an item matching is_even, but 2 did."
    )


def test_does_not_contain_matching_counts_the_rest() -> None:
    """One stray row and a systemic problem are different findings."""
    items = {1, 2, 4, 6}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).does_not_contain_matching(is_even)
    assert str(caught.value) == (
        "Expected items not to contain an item matching is_even,"
        " but 2 did (and so did 2 other items)."
    )


def test_contains_single_matching_continues_on_the_one_that_matched() -> None:
    subject = Bag({1, 2, 3})
    found = subject.contains_single_matching(is_even)
    assert found.subject == 2
    assert found.and_ is subject
    found.which.is_equal_to(2)


def test_contains_single_matching_rejects_a_second_match() -> None:
    """Where ``contains_matching`` would hand back whichever came first."""
    items = {1, 2, 4}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).contains_single_matching(is_even)
    assert str(caught.value) == (
        "Expected items to contain exactly one item matching is_even,"
        " but 2 items of 3 matched: [2, 4]."
    )


def test_contains_single_matching_reports_no_match_the_way_contains_matching_does() -> None:
    items = {1, 3}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).contains_single_matching(is_even)
    assert str(caught.value) == (
        "Expected items to contain exactly one item matching is_even,"
        " but checked 2 items and none matched: {1, 3}."
    )


def test_contains_single_matching_stops_at_the_second_match() -> None:
    """The happy path is one pass; the count in the message costs a second, on failure only.

    A predicate that records its calls is the only way to see the difference
    between "scanned once" and "scanned until it knew", and the second is what
    the assertion promises.
    """
    calls: list[int] = []

    def counted(value: int) -> bool:
        calls.append(value)
        return value in {1, 2}

    with pytest.raises(AssertionFailure):
        Bag((1, 2, 3, 4, 5)).contains_single_matching(counted)
    assert calls[:2] == [1, 2]
    assert len(calls) == 2 + 5, "the failure message re-scanned once, and only once"


def test_every_finding_assertion_absorbs_its_chain_the_same_way() -> None:
    """One root cause, one message: the item that was never found cannot be wrong too.

    These three report through ``_fail_narrowing``, and that is not decoration.
    ``_fail`` hands back the collection wrapper where a ``Found`` is declared, so
    in a soft scope ``.which`` would raise ``AttributeError`` from inside the
    library -- or, where it did not, the chain would report a second failure
    derived from the first. Every branch is exercised: nothing matched, and too
    many did.
    """
    odds = {1, 3}
    evens = {2, 4}
    pair = {1, 2}
    with soft_assertions() as scope:
        Bag(odds).contains_matching(is_even).which.is_equal_to(2)
        Bag(odds).contains_single_matching(is_even).which.is_equal_to(2)
        Bag(evens).contains_single_matching(is_even).which.is_equal_to(2)
        Bag(pair).contains_single().which.is_equal_to(1)
        collected = scope.discard()
    assert [message.partition(", but")[0] for message in collected] == [
        "Expected odds to contain an item matching is_even",
        "Expected odds to contain exactly one item matching is_even",
        "Expected evens to contain exactly one item matching is_even",
        "Expected pair to contain a single item",
    ]


def test_the_absorbed_subject_is_recognisable_if_it_ever_leaks() -> None:
    """The stand-in says what it is, so a leak is diagnosable rather than baffling."""
    odds = {1, 3}
    with soft_assertions() as scope:
        dead = Bag(odds).contains_matching(is_even)
        scope.discard()
    assert "narrowing failed" in repr(dead)


def test_does_not_contain_none() -> None:
    Bag({1, 2}).does_not_contain_none()
    items: set[int | None] = {None}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).does_not_contain_none()
    assert str(caught.value) == "Expected items not to contain None, but found one: {None}."


def test_does_not_contain_none_takes_a_key() -> None:
    """The question people actually have about a collection of rows."""
    rows = {"a": Row(1, "ana@example.com"), "b": Row(2, None)}
    Bag(rows.values()).does_not_contain_none()

    values = rows.values()
    with pytest.raises(AssertionFailure) as caught:
        Bag(values).does_not_contain_none(key=email_of)
    assert str(caught.value) == (
        "Expected values not to contain None under email_of, but Row(2) gave one: [Row(1), Row(2)]."
    )


def test_has_unique_items_is_a_real_question_on_a_dict_view() -> None:
    """Vacuous on a set; ``dict.values()`` is the unordered collection that can fail it.

    It is also the case that rules out the obvious implementation: a view cannot
    be indexed, so the repeat has to be carried out of the walk rather than
    fetched back out of the subject.
    """
    rows = {"a": 1, "b": 2}
    Bag(rows.values()).has_unique_items().and_.contains_no_duplicates()

    values = {"a": 1, "b": 1}.values()
    with pytest.raises(AssertionFailure) as caught:
        Bag(values).has_unique_items()
    assert (
        str(caught.value) == "Expected values to have unique items, but 1 appeared again: [1, 1]."
    )


def test_has_unique_items_copes_with_unhashable_items() -> None:
    """A collection of dicts is an ordinary test subject; refusing to check it is not an option."""
    rows: dict[str, dict[str, int]] = {"a": {"x": 1}, "b": {"x": 1}}
    with pytest.raises(AssertionFailure, match="appeared again"):
        Bag(rows.values()).has_unique_items()


def test_has_unique_items_takes_a_key_and_names_its_result() -> None:
    """Uniqueness of ``row.id``, which is what is actually wanted.

    The rows are distinct objects, so the un-keyed reading passes and reports
    nothing. The message names the id that came round twice, not the row: the
    row is one of several that collided and naming it buries the finding.
    """
    rows = {"a": Row(1, "a"), "b": Row(2, "b"), "c": Row(1, "c")}
    Bag(rows.values()).has_unique_items()

    values = rows.values()
    with pytest.raises(AssertionFailure) as caught:
        Bag(values).has_unique_items(key=row_id)
    assert str(caught.value) == (
        "Expected values to have unique items by row_id,"
        " but 1 appeared again: [Row(1), Row(2), Row(1)]."
    )


def test_an_anonymous_key_is_called_a_key_and_not_a_predicate() -> None:
    """``describe_predicate``'s fallback noun is wrong here, and the noun gets read."""
    rows = {"a": Row(1, "a"), "b": Row(1, "b")}
    values = rows.values()
    with pytest.raises(AssertionFailure) as caught:
        Bag(values).has_unique_items(key=lambda row: row.id)
    assert str(caught.value).startswith("Expected values to have unique items by the key, but 1")


def test_contains_no_duplicates_forwards_the_key_its_alias_takes() -> None:
    """An alias that dropped ``key`` would silently assert something weaker."""
    rows = {"a": Row(1, "a"), "b": Row(1, "b")}
    values = rows.values()
    with pytest.raises(AssertionFailure, match="unique items by row_id"):
        Bag(values).contains_no_duplicates(key=row_id)


def test_contains_items_of_type_means_all_of_them() -> None:
    Bag({"a"}).contains_items_of_type(str)
    mixed: set[object] = {1}
    with pytest.raises(AssertionFailure) as caught:
        Bag(mixed).contains_items_of_type(str)
    assert str(caught.value) == "Expected mixed to contain only instances of str, but 1 was int."


def test_does_not_contain_items_of_type_means_not_one_of_them() -> None:
    """*Not one*, not "not all of them" -- the weaker reading would pass on one offender."""
    Bag({1, 2}).does_not_contain_items_of_type(str)
    mixed: set[object] = {"a"}
    with pytest.raises(AssertionFailure) as caught:
        Bag(mixed).does_not_contain_items_of_type(str)
    assert str(caught.value) == (
        "Expected mixed not to contain any item of type str, but 'a' was str."
    )


def test_does_not_contain_items_of_type_counts_subclasses() -> None:
    """The mirror of ``all_are_instance_of``, so it reads ``isinstance`` the same way."""
    pets: set[Animal] = {Dog()}
    with pytest.raises(AssertionFailure) as caught:
        Bag(pets).does_not_contain_items_of_type(Animal)
    assert str(caught.value) == (
        "Expected pets not to contain any item of type Animal, but Dog() was Dog."
    )


def test_does_not_contain_items_of_type_passes_on_an_empty_collection() -> None:
    Bag(EMPTY).does_not_contain_items_of_type(int)


# ---------------------------------------------------------------------------
# Set-like relations: subset and intersection
# ---------------------------------------------------------------------------
def test_is_subset_of_lists_the_items_that_were_extra() -> None:
    Bag({1, 2}).is_subset_of([1, 2, 3])
    Bag(EMPTY).is_subset_of({1})
    items = {1, 2, 3}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).is_subset_of({1})
    assert str(caught.value) == "Expected items to be a subset of {1}, but also had [2, 3]."


def test_is_not_subset_of_says_why_an_empty_collection_fails_it() -> None:
    """An empty collection told that every item was in it reads like a library bug."""
    empty: set[int] = set()
    with pytest.raises(AssertionFailure) as caught:
        Bag(empty).is_not_subset_of({1})
    assert str(caught.value) == (
        "Expected empty not to be a subset of {1}, but it had no items "
        "-- an empty collection is a subset of anything."
    )


def test_intersects_and_does_not_intersect() -> None:
    Bag({1, 2}).intersects({2, 3})
    Bag({1, 2}).does_not_intersect({3, 4})
    items = {1, 2}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).intersects({8, 9})
    assert str(caught.value) == (
        "Expected items to intersect {8, 9}, but shared nothing with {1, 2}."
    )
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).does_not_intersect({1, 2})
    assert str(caught.value) == "Expected items not to intersect {1, 2}, but shared [1, 2]."


# ---------------------------------------------------------------------------
# Set-like relations: superset, the proper forms, disjointness
# ---------------------------------------------------------------------------
def test_is_superset_of_names_what_was_missing() -> None:
    """Both halves of the sentence read in sorted order, whatever the hash seed.

    ``{1, 8, 9}`` is written here in one order and printed in another, and that
    is the point: a set literal has no order to be faithful to, so the message
    imposes one instead of repeating whichever order this process happened to
    hash the members into.
    """
    Bag({1, 2, 3}).is_superset_of({1, 3})
    Bag({1, 2}).is_superset_of(EMPTY)
    items = {1, 2}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).is_superset_of({1, 8, 9})
    assert str(caught.value) == (
        "Expected items to be a superset of {1, 8, 9}, but was missing [8, 9]."
    )


def test_is_superset_of_ignores_repeats() -> None:
    """Membership, not multiplicity -- the reading ``is_subset_of`` takes too."""
    Bag([1, 1, 2]).is_superset_of([1, 2, 2])


def test_is_not_superset_of() -> None:
    Bag({1}).is_not_superset_of({1, 2})
    items = {1, 2}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).is_not_superset_of({1})
    assert str(caught.value) == (
        "Expected items not to be a superset of {1}, but it held every item: {1, 2}."
    )


def test_is_not_superset_of_says_why_an_empty_argument_fails_it() -> None:
    """The mirror of the empty-subject case ``is_not_subset_of`` explains."""
    items = {1, 2}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).is_not_superset_of(EMPTY)
    assert str(caught.value) == (
        "Expected items not to be a superset of set(), but there was nothing it could be "
        "missing -- everything is a superset of an empty collection."
    )


def test_is_proper_subset_of_needs_the_other_side_to_hold_more() -> None:
    Bag({1, 2}).is_proper_subset_of({1, 2, 3})
    items = {1, 2}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).is_proper_subset_of({1, 2})
    assert str(caught.value) == (
        "Expected items to be a proper subset of {1, 2}, but they held the same items."
    )
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).is_proper_subset_of({1})
    assert str(caught.value) == ("Expected items to be a proper subset of {1}, but also had [2].")


def test_is_proper_superset_of_needs_something_of_its_own() -> None:
    Bag({1, 2, 3}).is_proper_superset_of({1, 2})
    items = {1, 2}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).is_proper_superset_of({1, 2})
    assert str(caught.value) == (
        "Expected items to be a proper superset of {1, 2}, but they held the same items."
    )
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).is_proper_superset_of({1, 9})
    assert str(caught.value) == (
        "Expected items to be a proper superset of {1, 9}, but was missing [9]."
    )


def test_the_proper_relations_read_repeats_as_a_set_does() -> None:
    """``[1, 1]`` and ``[1]`` hold the same items, so neither is proper in the other."""
    with pytest.raises(AssertionFailure, match="held the same items"):
        Bag([1, 1]).is_proper_subset_of([1])
    with pytest.raises(AssertionFailure, match="held the same items"):
        Bag([1]).is_proper_superset_of([1, 1])


def test_is_disjoint_from_is_the_alias_does_not_intersect_is() -> None:
    """Same assertion, two spellings -- so they cannot report different things."""
    Bag({1, 2}).is_disjoint_from({3, 4})
    items = {1, 2}
    with pytest.raises(AssertionFailure) as by_alias:
        Bag(items).is_disjoint_from({2})
    with pytest.raises(AssertionFailure) as by_name:
        Bag(items).does_not_intersect({2})
    assert str(by_alias.value) == str(by_name.value)


def test_contains_only_is_exact_in_both_directions() -> None:
    """AssertJ's ``containsOnly`` and this library's ``contains_only_keys``, agreeing."""
    Bag({1, 2}).contains_only(1, 2)
    Bag({1, 2}).contains_only(2, 1)
    Bag([1, 1, 2]).contains_only(1, 2)

    items = {1, 2, 3}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).contains_only(1, 2)
    assert str(caught.value) == "Expected items to contain only (1, 2), but also had [3]."

    # One item still reads as a listing. Without the trailing comma the message
    # would say "to contain only (1)", which reads as the number 1.
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).contains_only(1)
    assert str(caught.value) == "Expected items to contain only (1,), but also had [2, 3]."

    with pytest.raises(AssertionFailure) as caught:
        Bag(items).contains_only(1, 2, 3, 4)
    assert str(caught.value) == (
        "Expected items to contain only (1, 2, 3, 4), but was missing [4]."
    )

    with pytest.raises(AssertionFailure) as caught:
        Bag(items).contains_only(1, 2, 9)
    assert str(caught.value) == (
        "Expected items to contain only (1, 2, 9), but was missing [9] and also had [3]."
    )


def test_contains_only_with_no_items_asserts_emptiness() -> None:
    """Not vacuous, so not a caller bug -- the exception ``contains_only_keys`` gets."""
    Bag(EMPTY).contains_only()
    items = {1}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).contains_only()
    assert str(caught.value) == "Expected items to contain only (), but also had [1]."


def test_contains_none_of_lists_the_ones_that_were_there() -> None:
    Bag({1, 2}).contains_none_of(8, 9)
    items = {1, 2, 3}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).contains_none_of(2, 3, 9)
    assert str(caught.value) == ("Expected items not to contain any of (2, 3, 9), but had [2, 3].")


def test_contains_none_of_with_no_items_is_a_caller_bug() -> None:
    """A variadic given nothing asserts nothing, so it is a bug in the test, not a failure."""
    with pytest.raises(ValueError, match="at least one") as caught:
        Bag({1}).contains_none_of()
    assert not isinstance(caught.value, AssertionFailure)


# ---------------------------------------------------------------------------
# Multi-item membership: the variadic spellings of the relations above
# ---------------------------------------------------------------------------
def test_contains_all_allows_extras_and_lists_what_was_missing() -> None:
    """Containment, not equality -- ``contains_only`` is the one that closes both ends."""
    Bag({1, 2, 3}).contains_all(1, 3)
    items = {1, 2}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).contains_all(1, 2, 3, 4)
    assert str(caught.value) == (
        "Expected items to contain all of (1, 2, 3, 4), but was missing [3, 4]."
    )


def test_does_not_contain_all_is_satisfied_by_one_absence() -> None:
    """The negation of ``contains_all``; ``contains_none_of`` is the strict one."""
    Bag({1, 2}).does_not_contain_all(1, 9)
    items = {1, 2}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).does_not_contain_all(1, 2)
    assert str(caught.value) == (
        "Expected items not to contain all of (1, 2), but it held every one of them: {1, 2}."
    )


def test_contains_any_needs_only_one() -> None:
    Bag({1, 2}).contains_any(9, 2)
    items = {1, 2}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).contains_any(8, 9)
    assert str(caught.value) == (
        "Expected items to contain at least one of (8, 9), but was {1, 2}."
    )


def test_the_variadic_pair_agrees_with_the_relation_it_mirrors() -> None:
    """They differ in wording, and must not be able to differ in the answer.

    Both go through the same helper, which is the only reason that is true; a
    second implementation is exactly how two assertions start answering the same
    question differently.
    """
    cases: list[tuple[set[int], tuple[int, ...]]] = [
        ({1, 2, 3}, (1, 3)),
        ({1, 2}, (1, 2, 3)),
        (set(), (1,)),
        ({1}, (1,)),
    ]
    for items, wanted in cases:
        assert passes(Bag(items).contains_all, *wanted) is passes(
            Bag(items).is_superset_of, set(wanted)
        )
        assert passes(Bag(items).contains_any, *wanted) is passes(
            Bag(items).intersects, set(wanted)
        )
        assert passes(Bag(items).does_not_contain_all, *wanted) is passes(
            Bag(items).is_not_superset_of, set(wanted)
        )


def test_there_is_no_does_not_contain_any_because_contains_none_of_is_it() -> None:
    """One name for this question here, and the mirror-image single name on strings.

    ``StringExpect`` has ``does_not_contain_any`` and no ``contains_none_of``;
    this subject has the reverse. If the fourth name is ever wanted here it
    should arrive as an alias of this assertion, the way ``is_disjoint_from``
    is one -- never as a second implementation, which is how two spellings of a
    question start giving two answers.
    """
    assert not hasattr(CollectionExpect, "does_not_contain_any")
    Bag({1, 2}).contains_none_of(8, 9)


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda: Bag({1}).contains_all(), id="contains_all"),
        pytest.param(lambda: Bag({1}).does_not_contain_all(), id="does_not_contain_all"),
        pytest.param(lambda: Bag({1}).contains_any(), id="contains_any"),
    ],
)
def test_the_new_variadics_reject_an_empty_call(call: object) -> None:
    """Assert nothing, or assert what nothing could satisfy: both are caller bugs."""
    with pytest.raises(ValueError, match="at least one") as caught:
        call()  # type: ignore[operator]  # pyright: ignore[reportCallIssue]
    assert not isinstance(caught.value, AssertionFailure)


# ---------------------------------------------------------------------------
# Element types
# ---------------------------------------------------------------------------
def test_all_are_instance_of_accepts_subclasses() -> None:
    pets: set[Animal] = {Dog()}
    Bag(pets).all_are_instance_of(Animal)
    mixed: set[object] = {"not a pet"}
    with pytest.raises(AssertionFailure) as caught:
        Bag(mixed).all_are_instance_of(Animal)
    assert str(caught.value) == (
        "Expected mixed to contain only instances of Animal, but 'not a pet' was str."
    )


def test_all_are_exactly_type_rejects_subclasses() -> None:
    pets: set[Animal] = {Dog()}
    with pytest.raises(AssertionFailure) as caught:
        Bag(pets).all_are_exactly_type(Animal)
    assert str(caught.value) == ("Expected pets to contain only Animal exactly, but Dog() was Dog.")


def test_all_equal_to() -> None:
    Bag({2}).all_equal_to(2)
    items = {2, 3}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).all_equal_to(2)
    assert str(caught.value) == "Expected items to contain only 2, but 3 did not match: {2, 3}."


def test_all_equal_to_compares_by_equality_not_identity() -> None:
    """``==``, not ``is``.

    The test above cannot tell the two apart: CPython interns small integers, so
    the ``2`` in the subject and the ``2`` in the argument are the same object
    and an implementation written with ``is`` would pass it. ``Weight`` is equal
    without being identical, which is the only way to ask the question.
    """
    Bag({Weight(5)}).all_equal_to(Weight(5))

    weights = {Weight(6)}
    with pytest.raises(AssertionFailure) as caught:
        Bag(weights).all_equal_to(Weight(5))
    assert str(caught.value) == (
        "Expected weights to contain only Weight(5), but Weight(6) did not match: {Weight(6)}."
    )


# ---------------------------------------------------------------------------
# Nested assertions
# ---------------------------------------------------------------------------
def test_all_satisfy_passes_and_chains() -> None:
    subject = Bag({2, 4})
    assert subject.all_satisfy(lambda value: expect(value).is_greater_than(1)) is subject


def test_all_satisfy_reports_every_failing_item_without_an_index() -> None:
    def is_two(value: int) -> None:
        expect(value).is_equal_to(2)

    items = {1, 2, 3}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).all_satisfy(is_two)
    message = str(caught.value)
    assert message.startswith("Expected items to satisfy the inspection for every item.\n")
    assert "  - Expected value to equal 2, but was 1" in message
    assert "  - Expected value to equal 2, but was 3" in message
    assert "index" not in message


def test_all_satisfy_lets_a_real_error_through() -> None:
    """A broken inspector is a bug in the test, not a finding about the subject."""
    with pytest.raises(ZeroDivisionError):
        Bag({1, 2}).all_satisfy(lambda value: value / 0)


def test_satisfies_in_any_order_matches_predicates_to_distinct_items() -> None:
    Bag({1, 2}).satisfies_in_any_order(lambda value: value == 2, lambda value: value == 1)


def test_satisfies_in_any_order_is_not_greedy() -> None:
    """The case a naive `any()` per predicate gets wrong, on an unordered subject."""
    Bag({1, 2}).satisfies_in_any_order(lambda value: value in (1, 2), lambda value: value == 1)


def test_satisfies_in_any_order_reports_the_predicate_left_unmatched() -> None:
    def is_one(value: int) -> bool:
        return value == 1

    items = {1, 2}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).satisfies_in_any_order(is_one, is_one)
    assert str(caught.value) == (
        "Expected items to satisfy every predicate in any order, "
        "but no unclaimed item matched is_one (predicate 2): {1, 2}."
    )


def test_satisfies_in_any_order_requires_matching_counts() -> None:
    items = {1, 2, 3}
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).satisfies_in_any_order(lambda value: value == 1)
    assert str(caught.value) == (
        "Expected items to have one item for each of the 1 predicate, but had 3: {1, 2, 3}."
    )


# ---------------------------------------------------------------------------
# Wildcard matching
# ---------------------------------------------------------------------------
def test_contains_match_uses_wildcards() -> None:
    rows = {"alpha": 1, "beta": 2}
    Bag(rows.keys()).contains_match("al*")
    Bag(rows.keys()).contains_match("bet?")
    lines = rows.keys()
    with pytest.raises(AssertionFailure) as caught:
        Bag(lines).contains_match("gam*")
    assert str(caught.value) == (
        "Expected lines to contain a match for 'gam*', but was ['alpha', 'beta']."
    )


def test_does_not_contain_match_names_the_item_but_not_a_position() -> None:
    Bag({"alpha"}).does_not_contain_match("bet*")
    lines = {"alpha": 1, "beta": 2}.keys()
    with pytest.raises(AssertionFailure) as caught:
        Bag(lines).does_not_contain_match("bet*")
    assert str(caught.value) == (
        "Expected lines not to contain a match for 'bet*', but 'beta' matched."
    )


def test_both_halves_of_the_wildcard_pair_are_case_sensitive() -> None:
    """The negation has to agree with the assertion about what "matches" means.

    Pinned on both, because they are two calls to ``matches_wildcard`` and only
    one of them was covered: an ``ignoring_case=True`` slipped into
    ``does_not_contain_match`` alone would leave the pair contradicting each
    other, and every other test in this file would still pass.
    """
    lines = {"ALPHA": 1}.keys()
    with pytest.raises(AssertionFailure) as caught:
        Bag(lines).contains_match("alpha*")
    assert str(caught.value) == (
        "Expected lines to contain a match for 'alpha*', but was ['ALPHA']."
    )
    Bag(lines).does_not_contain_match("alpha*")


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def test_each_kind_of_collection_still_looks_like_what_it_is() -> None:
    """The brackets are restored from the container's type, empty ones included."""
    cases: list[tuple[Collection[int], str]] = [
        ({1, 2}, "{1, 2}"),
        (frozenset({1, 2}), "frozenset({1, 2})"),
        (set(), "set()"),
        (frozenset(), "frozenset()"),
        ([1, 2], "[1, 2]"),
        ((1, 2), "(1, 2)"),
        ({1: 1}.values(), "[1]"),
    ]
    for items, rendered in cases:
        with pytest.raises(AssertionFailure) as caught:
            Bag(items).contains(99)
        assert str(caught.value) == "Expected items to contain 99, but was " + rendered + "."


def test_a_long_collection_is_truncated_in_the_message() -> None:
    numbers = set(range(30))
    with pytest.raises(AssertionFailure) as caught:
        Bag(numbers).is_empty()
    assert str(caught.value) == (
        "Expected numbers to be empty, but was [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, ... (20 more)]."
    )


def test_nested_findings_are_capped_the_way_collections_are() -> None:
    """A failing inspection over a long collection must not print a line per item."""
    items = set(range(25))
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).all_satisfy(lambda value: expect(value).is_equal_to(-1))
    message = str(caught.value)
    assert "  - Expected the value to equal -1, but was 9" in message
    assert message.endswith("  - ... (15 more items failed)")


# ---------------------------------------------------------------------------
# Chaining and narrowing
# ---------------------------------------------------------------------------
def test_a_chain_keeps_returning_the_same_subject() -> None:
    subject = Bag({1, 2, 3})
    assert subject.is_not_empty().and_.has_length(3).and_.contains(2) is subject
    assert subject.subject == {1, 2, 3}


def test_the_generic_catalogue_is_inherited() -> None:
    """``CollectionExpect`` is an ``Expect`` first: equality and identity still work."""
    tags = {"a"}
    subject = Bag(tags)
    assert subject.is_equal_to({"a"}).and_.is_same_as(tags).subject is tags


# ---------------------------------------------------------------------------
# extracting
# ---------------------------------------------------------------------------
def test_extracting_asserts_about_a_field_of_every_item() -> None:
    rows = {"a": Row(1, "a"), "b": Row(2, "b")}
    Bag(rows.values()).extracting(row_id).contains_only(1, 2)


def test_extracting_reports_against_the_extracted_values() -> None:
    """The failure is about the ids, because that is what the assertion was about."""
    rows = {"a": Row(1, "a"), "b": Row(2, "b")}
    with pytest.raises(AssertionFailure) as caught:
        Bag(rows.values()).extracting(row_id).contains(9)
    assert str(caught.value).endswith("to contain 9, but was [1, 2].")


def test_extracting_hands_back_the_order_free_subject() -> None:
    """The trap the return type exists to close.

    The extracted list is materialised, so a sequence subject would type-check
    and would let ``is_sorted`` be asked of a ``set``'s iteration order. The
    order-free source gives an order-free result; ``SequenceExpect`` overrides it
    and ``tests/test_sequence.py`` pins that half.
    """
    subject = Bag({1, 2}).extracting(str)
    assert isinstance(subject, CollectionExpect)
    assert not isinstance(subject, SequenceExpect)
    assert not hasattr(subject, "is_sorted")


def test_extracting_can_be_chained() -> None:
    rows = {"a": Row(1, "a"), "b": Row(22, "b")}
    Bag(rows.values()).extracting(row_id).extracting(str).contains_only("1", "22")


def test_extracting_lets_a_broken_selector_through() -> None:
    """A selector that raises is a bug in the test, not a finding about the subject."""

    def explode(_row: Row) -> int:
        raise RuntimeError("boom")

    rows = {"a": Row(1, "a")}
    with pytest.raises(RuntimeError, match="boom"):
        Bag(rows.values()).extracting(explode)


def test_extracting_keeps_an_explicitly_given_subject_name() -> None:
    """A new wrapper has no name, and dropping the given one inverts the fallback.

    Recovery reads the source line and finds ``expect(rows)``, which is the right
    answer often enough that the failure above pins it. It is the *wrong* answer
    in the two places ``described_as`` exists for -- a loop, a helper -- so an
    explicit name has to outlive the transformation, or naming a subject buys
    less than not transforming it.
    """
    batches = [{"a": Row(1, "a")}, {"b": Row(2, "b")}]
    for index, batch in enumerate(batches):
        with pytest.raises(AssertionFailure) as caught:
            Bag(batch.values()).described_as(f"batches[{index}]").extracting(row_id).contains(9)
        assert str(caught.value).startswith(f"Expected batches[{index}] to contain 9")


def test_extracting_takes_no_because_because_it_asserts_nothing() -> None:
    """``because`` belongs to assertions; a transformation makes no claim and cannot fail.

    Asked of a bound method rather than of ``CollectionExpect.extracting``: the
    unsubscripted class leaves ``E`` unsolved, and a signature read off it is
    partially unknown -- which pyright's strict mode rejects, rightly.
    """
    assert "because" not in inspect.signature(Bag({1}).extracting).parameters


def test_the_string_form_of_extracting_is_absent_on_purpose() -> None:
    """assertpy's ``extracting("name")`` is untypeable, so it is not offered.

    A string cannot tell a checker that the attribute exists, still less what
    type it has, so everything downstream of it would be checked against
    ``Any``. Passing one is a type error statically; at runtime it reaches
    ``str.__call__``, which does not exist -- and that is the honest outcome,
    rather than a silent ``getattr`` that makes the untyped form work.
    """
    rows = {"a": Row(1, "a")}
    with pytest.raises(TypeError):
        Bag(rows.values()).extracting("id")  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]


# ---------------------------------------------------------------------------
# No message claims a position (the point of the split)
# ---------------------------------------------------------------------------
#: One failing call per assertion the class declares, used three times: to prove
#: every one of them carries the caller's `because` reason into its message, to
#: prove no message names a position, and to prove the table itself has not
#: fallen behind the catalogue. Each `id` is the method's real name, which is
#: what makes the last one possible.
BECAUSE_CALLS: Final = [
    pytest.param(lambda: Bag({1}).is_empty(because="R"), id="is_empty"),
    pytest.param(lambda: Bag(EMPTY).is_not_empty(because="R"), id="is_not_empty"),
    pytest.param(lambda: Bag({1}).is_none_or_empty(because="R"), id="is_none_or_empty"),
    pytest.param(lambda: Bag(EMPTY).is_not_none_or_empty(because="R"), id="is_not_none_or_empty"),
    pytest.param(lambda: Bag({1}).has_length(2, because="R"), id="has_length"),
    pytest.param(lambda: Bag({1}).does_not_have_length(1, because="R"), id="does_not_have_length"),
    pytest.param(
        lambda: Bag({1}).has_length_matching(lambda n: n > 1, because="R"),
        id="has_length_matching",
    ),
    pytest.param(
        lambda: Bag({1}).has_length_greater_than(2, because="R"), id="has_length_greater_than"
    ),
    pytest.param(
        lambda: Bag({1}).has_length_greater_than_or_equal_to(2, because="R"),
        id="has_length_greater_than_or_equal_to",
    ),
    pytest.param(lambda: Bag({1}).has_length_less_than(1, because="R"), id="has_length_less_than"),
    pytest.param(
        lambda: Bag({1}).has_length_less_than_or_equal_to(0, because="R"),
        id="has_length_less_than_or_equal_to",
    ),
    pytest.param(lambda: Bag({1}).has_same_length_as([], because="R"), id="has_same_length_as"),
    pytest.param(
        lambda: Bag({1}).does_not_have_same_length_as([2], because="R"),
        id="does_not_have_same_length_as",
    ),
    pytest.param(lambda: Bag({1}).contains(2, because="R"), id="contains"),
    pytest.param(lambda: Bag({1}).does_not_contain(1, because="R"), id="does_not_contain"),
    pytest.param(lambda: Bag({1, 2}).contains_single(because="R"), id="contains_single"),
    pytest.param(lambda: Bag({1}).only_contains(lambda v: v > 1, because="R"), id="only_contains"),
    pytest.param(lambda: Bag({1}).contains_matching(is_even, because="R"), id="contains_matching"),
    pytest.param(
        lambda: Bag({2}).does_not_contain_matching(is_even, because="R"),
        id="does_not_contain_matching",
    ),
    pytest.param(
        lambda: Bag({2, 4}).contains_single_matching(is_even, because="R"),
        id="contains_single_matching",
    ),
    pytest.param(
        lambda: Bag({1}).contains_items_of_type(str, because="R"), id="contains_items_of_type"
    ),
    pytest.param(
        lambda: Bag({1}).does_not_contain_items_of_type(int, because="R"),
        id="does_not_contain_items_of_type",
    ),
    pytest.param(
        lambda: Bag({None}).does_not_contain_none(because="R"),
        id="does_not_contain_none",
    ),
    pytest.param(
        lambda: Bag({"a": 1, "b": 1}.values()).has_unique_items(because="R"),
        id="has_unique_items",
    ),
    pytest.param(
        lambda: Bag({"a": 1, "b": 1}.values()).contains_no_duplicates(because="R"),
        id="contains_no_duplicates",
    ),
    pytest.param(lambda: Bag({1}).is_subset_of(EMPTY, because="R"), id="is_subset_of"),
    pytest.param(lambda: Bag({1}).is_not_subset_of({1}, because="R"), id="is_not_subset_of"),
    pytest.param(lambda: Bag({1}).is_superset_of({2}, because="R"), id="is_superset_of"),
    pytest.param(lambda: Bag({1}).is_not_superset_of({1}, because="R"), id="is_not_superset_of"),
    pytest.param(lambda: Bag({1}).is_proper_subset_of({1}, because="R"), id="is_proper_subset_of"),
    pytest.param(
        lambda: Bag({1}).is_proper_superset_of({1}, because="R"), id="is_proper_superset_of"
    ),
    pytest.param(lambda: Bag({1}).intersects({2}, because="R"), id="intersects"),
    pytest.param(lambda: Bag({1}).does_not_intersect({1}, because="R"), id="does_not_intersect"),
    pytest.param(lambda: Bag({1}).is_disjoint_from({1}, because="R"), id="is_disjoint_from"),
    pytest.param(lambda: Bag({1}).contains_only(2, because="R"), id="contains_only"),
    pytest.param(lambda: Bag({1}).contains_none_of(1, because="R"), id="contains_none_of"),
    pytest.param(lambda: Bag({1}).contains_all(1, 2, because="R"), id="contains_all"),
    pytest.param(lambda: Bag({1}).does_not_contain_all(1, because="R"), id="does_not_contain_all"),
    pytest.param(lambda: Bag({1}).contains_any(9, because="R"), id="contains_any"),
    pytest.param(lambda: Bag({1}).all_are_instance_of(str, because="R"), id="all_are_instance_of"),
    pytest.param(
        lambda: Bag({1}).all_are_exactly_type(str, because="R"), id="all_are_exactly_type"
    ),
    pytest.param(lambda: Bag({1}).all_equal_to(2, because="R"), id="all_equal_to"),
    pytest.param(
        lambda: Bag({1}).all_satisfy(lambda v: expect(v).is_equal_to(2), because="R"),
        id="all_satisfy",
    ),
    pytest.param(lambda: Bag({1}).satisfies_in_any_order(because="R"), id="satisfies_in_any_order"),
    pytest.param(lambda: Bag({"a"}).contains_match("b", because="R"), id="contains_match"),
    pytest.param(
        lambda: Bag({"a"}).does_not_contain_match("a", because="R"), id="does_not_contain_match"
    ),
]


@pytest.mark.parametrize("call", BECAUSE_CALLS)
def test_because_reaches_every_assertion(call: object) -> None:
    with pytest.raises(AssertionFailure, match="because R"):
        call()  # type: ignore[operator]  # pyright: ignore[reportCallIssue]


@pytest.mark.parametrize("call", BECAUSE_CALLS)
def test_no_failure_message_claims_a_position(call: object) -> None:
    """The whole reason this class exists: an item of a set is not *at* anywhere.

    The inherited half reports positions through ``_position``/``_finding_tag``,
    which are empty here and overridden in the sequence subject. Anything that
    writes ``at index`` directly would slip past every other test in this file and
    be caught by this one.
    """
    with pytest.raises(AssertionFailure) as caught:
        call()  # type: ignore[operator]  # pyright: ignore[reportCallIssue]
    assert "index" not in str(caught.value)


#: Public methods that are **not** assertions. They make no claim, so they cannot
#: fail and have no `because` to carry -- only an assertion takes one. Listed
#: rather than detected, so that adding a second one is a deliberate act: an assertion
#: that quietly landed here would lose its `because` coverage and its message.
NOT_ASSERTIONS: Final = frozenset({"extracting"})


def test_the_because_table_has_not_fallen_behind_the_catalogue() -> None:
    """A new assertion must arrive with its `because` case, or this fails.

    What this subject declares rather than everything it answers to -- the
    inherited half of the surface belongs to `Expect` and is covered by its own
    tests, and the order-dependent half belongs to `SequenceExpect` and to
    `tests/test_sequence.py`.

    Its own seams count as its own. A subject is assembled from one mixin per
    seam, so `vars()` on it holds nothing at all, and asking that way would have
    compared the table against an empty set and passed.
    """
    covered = {parameters.id for parameters in BECAUSE_CALLS}
    declared = {
        name
        for name, attribute in declared_by_the_subject(CollectionExpect).items()
        if not name.startswith("_") and callable(attribute)
    } - NOT_ASSERTIONS
    assert covered == declared


def test_everything_excused_from_the_because_table_really_is_declared() -> None:
    """The excuse list cannot outlive what it excuses, or it starts hiding regressions."""
    assert set(declared_by_the_subject(CollectionExpect)) >= NOT_ASSERTIONS


# ---------------------------------------------------------------------------
# A passing assertion never reaches the failure path
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("no_failure_machinery")
def test_passing_collection_assertions_never_touch_the_failure_path() -> None:
    """``all_satisfy`` is absent on purpose.

    It routes its inner assertions through the collector by design, so it is the
    one that legitimately reads the ``ContextVar`` on the way past.
    """
    items = {1, 2, 3}
    Bag(items).is_not_empty().and_.has_length(3)
    Bag(EMPTY).is_empty().and_.is_none_or_empty()
    Bag(items).is_not_none_or_empty().and_.does_not_have_length(2)
    Bag(items).has_length_matching(lambda count: count == 3)
    Bag(items).has_length_greater_than(2).and_.has_length_greater_than_or_equal_to(3)
    Bag(items).has_length_less_than(4).and_.has_length_less_than_or_equal_to(3)
    Bag(items).has_same_length_as("abc").and_.does_not_have_same_length_as([1])
    Bag(items).contains(2).and_.does_not_contain(9)
    Bag(items).has_unique_items().and_.contains_no_duplicates()
    Bag(items).does_not_contain_none().and_.contains_items_of_type(int)
    Bag(items).is_subset_of({1, 2, 3}).and_.intersects({3})
    Bag(items).is_not_subset_of({1}).and_.does_not_intersect({9})
    Bag(items).is_superset_of({1}).and_.is_not_superset_of({9})
    Bag(items).is_proper_subset_of({1, 2, 3, 4}).and_.is_proper_superset_of({1})
    Bag(items).is_disjoint_from({9}).and_.contains_none_of(9)
    Bag(items).contains_only(1, 2, 3)
    Bag(items).all_are_instance_of(int).and_.only_contains(lambda value: value > 0)
    Bag(items).all_are_exactly_type(int)
    Bag({2}).all_equal_to(2)
    Bag(items).satisfies_in_any_order(
        lambda value: value == 1, lambda value: value == 2, lambda value: value == 3
    )
    Bag({7}).contains_single()
    Bag({"a"}).contains_match("?").and_.does_not_contain_match("bb*")
    Bag(items).contains_all(1, 2).and_.contains_any(3, 9)
    Bag(items).does_not_contain_all(1, 9)
    Bag(items).does_not_contain_items_of_type(str)
    Bag(items).contains_matching(is_even).and_.does_not_contain_matching(lambda value: value > 9)
    Bag({2, 3}).contains_single_matching(is_even)
    Bag(items).has_unique_items(key=str).and_.contains_no_duplicates(key=str)
    Bag(items).does_not_contain_none(key=str)
    Bag(items).extracting(str).contains("1")
    Bag(VOTES.values()).contains("ada", occurrences=twice)
    Bag(VOTES.values()).does_not_contain("ada", occurrences=once)


# ---------------------------------------------------------------------------
# How much a failure prints (lovely_assertions._formatting)
# ---------------------------------------------------------------------------
#: Fifteen items -- more than the default ten -- in a dict view, whose iteration
#: order is fixed, so the elision lands in a known place and the message can be
#: asserted whole.
MANY: Final = {str(number): number for number in range(15)}

#: The rendering of ``MANY.values()`` at the default bound, and in full.
TRUNCATED: Final = "[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, ... (5 more)]"
COMPLETE: Final = "[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]"


def test_a_long_collection_is_truncated_by_default() -> None:
    items = MANY.values()
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).contains(99)
    assert str(caught.value) == "Expected items to contain 99, but was " + TRUNCATED + "."


def test_widening_max_items_prints_more_of_the_collection() -> None:
    """The whole point of the option, proved from outside the library.

    Ten items is right for a message being skimmed and exactly wrong for the one
    being debugged: a fifteen-row failure that shows ten is least helpful when the
    row that matters is the fifteenth.
    """
    items = MANY.values()
    with formatting(max_items=15), pytest.raises(AssertionFailure) as caught:
        Bag(items).contains(99)
    assert str(caught.value) == "Expected items to contain 99, but was " + COMPLETE + "."


def test_narrowing_max_items_prints_less() -> None:
    """The bound goes both ways; the count of what was left out follows it."""
    items = MANY.values()
    with formatting(max_items=2), pytest.raises(AssertionFailure) as caught:
        Bag(items).contains(99)
    assert str(caught.value) == "Expected items to contain 99, but was [0, 1, ... (13 more)]."


def test_the_bound_is_read_where_the_message_is_built() -> None:
    """Not captured at import, and not at subject construction either.

    The subject here is built outside the scope and asserted on inside it, which
    is the shape a fixture-built subject really takes.
    """
    items = MANY.values()
    subject = Bag(items)
    with formatting(max_items=15), pytest.raises(AssertionFailure) as caught:
        subject.contains(99)
    assert str(caught.value).endswith(COMPLETE + ".")


def test_a_scope_changes_what_is_printed_and_never_what_is_decided() -> None:
    """Raising or lowering a bound cannot turn a pass into a failure."""
    items = MANY.values()
    with formatting(max_items=1):
        Bag(items).contains(3).and_.does_not_contain(99)
        assert not passes(Bag(items).contains, 99)
    with formatting(max_items=500):
        Bag(items).contains(3).and_.does_not_contain(99)
        assert not passes(Bag(items).contains, 99)


def test_every_collection_message_reads_the_same_bound() -> None:
    """``render_items`` renders them all, so one option governs the lot."""
    items = MANY.values()
    calls: list[Callable[[], object]] = [
        lambda: Bag(items).is_empty(),
        lambda: Bag(items).has_length(99),
        lambda: Bag(items).contains(99),
        lambda: Bag(items).does_not_contain(3),
    ]
    with formatting(max_items=15):
        for call in calls:
            with pytest.raises(AssertionFailure) as caught:
                call()
            assert COMPLETE in str(caught.value)


def test_the_nested_findings_listing_is_capped_by_the_same_bound() -> None:
    """``all_satisfy`` reports one line per failing item, and that is a listing too."""

    def over_a_hundred(value: int) -> object:
        return expect(value).is_greater_than(100)

    items = MANY.values()
    with pytest.raises(AssertionFailure) as caught:
        Bag(items).all_satisfy(over_a_hundred)
    assert "  - ... (5 more items failed)" in str(caught.value)

    with formatting(max_items=15), pytest.raises(AssertionFailure) as caught:
        Bag(items).all_satisfy(over_a_hundred)
    assert "more items failed" not in str(caught.value)
    assert str(caught.value).count("\n  - ") == 15


def test_the_mapping_previews_are_governed_by_the_same_option() -> None:
    """A view is a collection subject, so a widened bound reaches it too."""
    with formatting(max_items=15), pytest.raises(AssertionFailure) as caught:
        Bag(MANY.keys()).contains("99")
    assert "'14'" in str(caught.value)


def test_an_open_scope_costs_a_passing_assertion_nothing() -> None:
    """A passing assertion allocates nothing, and the option must not change that.

    ``tests/test_performance_invariants.py`` measures this outside a scope; what
    it cannot see is a scope putting a ``ContextVar`` read on the hot path.
    """
    baseline = blocks_allocated(lambda: None)
    subject = Bag({1, 2, 3})
    with formatting(max_items=100):
        assert blocks_allocated(lambda: subject.contains(2)) <= baseline
        assert blocks_allocated(subject.is_not_empty) <= baseline
        assert blocks_allocated(lambda: subject.has_length(3)) <= baseline


# ---------------------------------------------------------------------------
# Membership against a list, and what a hash table is not allowed to change
# ---------------------------------------------------------------------------
#
# `item in some_list` is a scan, so asking it once per item makes every set-like
# relation here O(n * m), and a failing `is_subset_of` over two lists of a couple
# of hundred thousand items runs long enough to look like a hang. `_searchable`
# hashes the container once instead, and the whole difficulty is that a set is
# *not* a drop-in for `in`.
#
# So these tests come in two halves. The first proves the table is really used --
# without it the second half proves nothing at all, because a gate that never
# opens trivially preserves every answer. The second asks the same question twice
# of the same values, once below the gate and once above it, and insists the two
# verdicts agree.


class Ledger:
    """Value equality with an identity hash -- the ORM row.

    ``a == b`` and ``hash(a) != hash(b)``. Python documents that pair as an
    invariant and this type breaks it deliberately, which is what every mapper
    that identifies rows by primary key and hashes them by object identity does.
    A scan finds ``b`` in ``[a]``; a set does not, and the difference is a
    *silently wrong answer* rather than an error.
    """

    __slots__ = ("key",)

    def __init__(self, key: int, /) -> None:
        self.key = key

    def __repr__(self) -> str:
        return "Ledger(" + str(self.key) + ")"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Ledger) and other.key == self.key

    def __hash__(self) -> int:
        return object.__hash__(self)


class Anything:
    """Equal to everything, hashed like nothing.

    Membership compares ``element == needle`` and falls back to the reflected
    ``needle == element``, so this is found in a list of strings. It is not found
    in a *set* of them: the lookup goes to its own hash bucket and never meets
    them. It is the case that proves the needles have to be checked and not only
    the container.
    """

    __slots__ = ()

    def __repr__(self) -> str:
        return "Anything()"

    def __eq__(self, other: object) -> bool:
        _ = other
        return True

    def __hash__(self) -> int:
        return 0


class Shout(str):
    """A ``str`` subclass whose equality ignores case while its hash does not.

    Which is why :data:`~lovely_assertions._collection._hashing._HASH_SAFE` names types
    *exactly* rather than through ``isinstance``: a subclass may override either
    half of the pair, and this one overrides the half that a set does not consult.
    ``Shout("A")`` is in ``["a"]`` and is not in ``{"a"}``.
    """

    __slots__ = ()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, str) and self.casefold() == other.casefold()

    def __hash__(self) -> int:
        return str.__hash__(self)


#: The same object twice, which is the only way a NaN is ever *in* anything.
THE_NAN: Final = float("nan")

#: Hash-safe filler, long enough to open both halves of the gate when it is added
#: to a container and to a list of lookups. Integers, because the point of the
#: filler is to be uninteresting.
FILLER: Final[list[object]] = list(range(max(_HASHING_PAYS_FROM, _REPEATED_LOOKUPS_FROM) * 2))


def _is_subset(subject: list[object], other: list[object], /) -> bool:
    try:
        Bag(subject).is_subset_of(other)
    except AssertionFailure:
        return False
    return True


#: ``(name, subject, other, verdict, hashed)``. ``verdict`` is what ``in`` says --
#: the answer both paths owe. ``hashed`` is whether the table is expected to open
#: for the padded form, and it is asserted, so a row cannot quietly stop
#: exercising the path it was written for.
ACROSS_THE_GATE: Final[list[tuple[str, list[object], list[object], bool, bool]]] = [
    ("plain values, present", [1, "a"], [1, "a", 2], True, True),
    ("plain values, one missing", [1, 999], [1, "a"], False, True),
    ("the same NaN object", [THE_NAN], [THE_NAN], True, True),
    ("a different NaN", [float("nan")], [THE_NAN], False, True),
    ("value equality, identity hash", [Ledger(1)], [Ledger(1)], True, False),
    ("an unhashable item in the container", [1], [[2], 1], True, False),
    ("an unhashable needle", [[9]], [1, 2], False, False),
    ("a needle that equals anything", [Anything()], ["a"], True, False),
    ("a container item that equals anything", ["a"], [Anything()], True, False),
    ("a str subclass that redefines equality", [Shout("A")], ["a"], True, False),
]


@pytest.mark.parametrize(
    ("subject", "other", "verdict", "hashed"),
    [(row[1], row[2], row[3], row[4]) for row in ACROSS_THE_GATE],
    ids=[row[0] for row in ACROSS_THE_GATE],
)
def test_the_hash_table_answers_exactly_what_the_scan_answers(
    subject: list[object], other: list[object], *, verdict: bool, hashed: bool
) -> None:
    """One question, asked below the gate and above it.

    Padding both sides with the same hash-safe integers cannot change whether
    every item of ``subject`` is in ``other``, so the short form and the long form
    are two askings of one question -- and only one of them can reach the table.

    ``verdict`` is not the library's own answer written down: it is what
    ``item in other`` says, which is the rule this module follows throughout.
    A row where the two differ is a row where making membership faster changed
    what it means.
    """
    padded_subject = [*subject, *FILLER]
    padded_other = [*other, *FILLER]
    assert _is_subset(subject, other) is verdict
    assert _is_subset(padded_subject, padded_other) is verdict
    assert isinstance(searchable(padded_subject, padded_other), set) is hashed


def test_a_long_enough_container_with_enough_lookups_is_hashed() -> None:
    """Otherwise every test above is a test of the scan twice over."""
    container = list(range(_HASHING_PAYS_FROM))
    lookups = list(range(_REPEATED_LOOKUPS_FROM))
    assert isinstance(searchable(lookups, container), set)


def test_a_short_container_is_left_alone() -> None:
    container = list(range(_HASHING_PAYS_FROM - 1))
    lookups = list(range(_REPEATED_LOOKUPS_FROM))
    assert searchable(lookups, container) is container


def test_too_few_lookups_never_pay_for_a_table() -> None:
    """A long container is not on its own a reason to hash it.

    ``contains_any("x")`` against a hundred-thousand-item list is *one* lookup.
    Hashing the whole list to answer it is five times slower than the scan it
    replaces, so the gate counts the lookups as well as the items.
    """
    container = list(range(100_000))
    lookups = list(range(_REPEATED_LOOKUPS_FROM - 1))
    assert searchable(lookups, container) is container


def test_enough_lookups_is_not_enough_when_the_container_dwarfs_them() -> None:
    """A lookup floor on its own does not bound what the table can cost.

    Deciding to hash is ``O(n)`` -- the type check walks the container and the
    build walks it again -- and it is spent whichever way the decision goes. A
    scan is not ``O(n)`` per lookup: it stops where it finds the item. So sixteen
    lookups is a reason to hash a container of a hundred items and not a reason to
    hash a container of a hundred thousand, and nothing about the *count* of the
    lookups can tell those two apart.
    """
    lookups = list(range(_REPEATED_LOOKUPS_FROM))
    just_wide_enough = list(range(_REPEATED_LOOKUPS_FROM * _LONGEST_CONTAINER_PER_LOOKUP))
    one_item_too_wide = [*just_wide_enough, -1]

    assert isinstance(searchable(lookups, just_wide_enough), set)
    assert searchable(lookups, one_item_too_wide) is one_item_too_wide


#: A hundred and sixty times the ~1.2us the scan actually needs, and eighteen
#: times *under* the 3.6ms an ungated table costs on the same call. Neither a
#: loaded machine nor a fast one can move the verdict.
_FRONT_LOADED_BUDGET_SECONDS: Final = 0.0002


def test_needles_at_the_front_are_not_paid_for_by_hashing_everything_behind_them() -> None:
    """The shape a gate counting only lookups gets catastrophically wrong.

    An early slice of a sorted collection is an ordinary thing to assert about,
    and it is the scan's best case: sixteen comparisons, one per needle, and it
    never touches the other ninety-nine thousand items. Hashing to answer it walks
    all hundred thousand twice -- measured at 1.2us against 3.6ms, three thousand
    times slower, and the ratio grows with the container rather than settling.
    """
    container = list(range(100_000))
    at_the_front = list(range(_REPEATED_LOOKUPS_FROM))

    assert searchable(at_the_front, container) is container

    started = time.perf_counter()
    Bag(at_the_front).is_subset_of(container)
    elapsed = time.perf_counter() - started

    assert elapsed < _FRONT_LOADED_BUDGET_SECONDS, (
        f"{_REPEATED_LOOKUPS_FROM} lookups at the front of a {len(container)}-item list "
        f"took {elapsed * 1e6:.1f}us, past the {_FRONT_LOADED_BUDGET_SECONDS * 1e6:.0f}us "
        f"budget. A scan stops where it finds the item; building a table does not -- "
        f"see `_LONGEST_CONTAINER_PER_LOOKUP`."
    )


def test_a_set_is_never_hashed_a_second_time() -> None:
    """It already answers in constant time; hashing it again is pure loss."""
    container = set(range(_HASHING_PAYS_FROM * 2))
    lookups = list(range(_REPEATED_LOOKUPS_FROM))
    assert searchable(lookups, container) is container


def test_a_tuple_is_hashed_the_way_a_list_is() -> None:
    """``contains_all(*items)`` hands its operands over as a tuple."""
    container = tuple(range(_HASHING_PAYS_FROM))
    lookups = list(range(_REPEATED_LOOKUPS_FROM))
    assert isinstance(searchable(lookups, container), set)


def test_the_values_view_is_hashed_and_the_other_two_views_are_not() -> None:
    """The one dict view with no index of its own.

    ``keys`` is the dictionary's lookup and ``items`` is that lookup plus a
    comparison; ``values`` walks. Measured over a fifty-thousand-entry dictionary,
    one lookup of the last value took 431us against 43ns for the same
    dictionary's keys -- so a values view is the one place a mapping subject can
    still be quadratic, and it is a collection subject in its own right.
    """
    mapping = {index: index for index in range(_HASHING_PAYS_FROM)}
    lookups = list(range(_REPEATED_LOOKUPS_FROM))
    assert isinstance(searchable(lookups, mapping.values()), set)
    assert searchable(lookups, mapping.keys()) is not None
    assert not isinstance(searchable(lookups, mapping.keys()), set)
    assert not isinstance(searchable(lookups, mapping.items()), set)
    Bag(mapping.values()).is_superset_of(lookups)


def test_a_nan_is_found_where_it_actually_is_however_long_the_collection() -> None:
    """The rule this module follows throughout, here through the hashed path.

    ``in`` is ``x is y or x == y``, and a set keeps the identity half: CPython
    compares the stored pointer before it compares the objects, and since 3.10 a
    float NaN hashes by identity, so the lookup lands in the bucket its own object
    is in. That is measured here rather than assumed, because the opposite is the
    obvious guess and it is the one that would have made this optimisation
    unsafe.
    """
    holder = [*FILLER, THE_NAN]
    lookups = [*FILLER, THE_NAN]
    assert isinstance(searchable(lookups, holder), set)
    Bag(lookups).is_subset_of(holder)
    Bag(holder).contains(THE_NAN)
    with pytest.raises(AssertionFailure):
        Bag(holder).contains(float("nan"))


def test_a_row_hashed_by_identity_is_still_found_by_value() -> None:
    """The wrong answer a type-blind ``set(container)`` would ship.

    Stated on its own as well as in the table, because it is the one that costs
    nothing to get wrong and is impossible to notice: no exception, no message, a
    green test that should have been red.
    """
    holder: list[object] = [*FILLER, Ledger(1)]
    lookups: list[object] = [*FILLER, Ledger(1)]
    assert searchable(lookups, holder) is holder
    Bag(lookups).is_subset_of(holder)
    Bag(holder).contains(Ledger(1))


def test_an_unhashable_needle_is_answered_rather_than_raised() -> None:
    """``["x"] in ["a"]`` is ``False``; ``["x"] in {"a"}`` is a ``TypeError``.

    A caller looking for a list inside a collection of strings has asked a
    question with an answer, and "no" is it.
    """
    holder: list[object] = [*FILLER, "a"]
    lookups: list[object] = [*FILLER, [9]]
    assert searchable(lookups, holder) is holder
    with pytest.raises(AssertionFailure):
        Bag(lookups).is_subset_of(holder)
    Bag(holder).does_not_contain([9])


#: Thirty thousand items. Quadratic, that is about two and a half seconds; linear
#: it is under three milliseconds. Two orders of magnitude below the budget and
#: five times above it: a loaded machine cannot reach the budget by being slow,
#: and a return to the scan cannot miss it by being fast.
_QUADRATIC_SUBJECT_SIZE: Final = 30_000
_QUADRATIC_BUDGET_SECONDS: Final = 0.5


def test_membership_against_a_long_list_is_not_quadratic() -> None:
    """Set-like membership over two long lists stays linear, in all three helpers.

    ``_none_outside`` answers the passing subset; ``_items_outside`` the failing
    one -- the *second* scan, on the failure path, and so half of what a
    quadratic failure costs -- and ``_any_inside`` the disjointness, which cannot
    exit early and so is the one with no fast case of its own.
    """
    left: list[object] = list(range(_QUADRATIC_SUBJECT_SIZE))
    right: list[object] = list(range(_QUADRATIC_SUBJECT_SIZE))
    missing: list[object] = [*range(_QUADRATIC_SUBJECT_SIZE - 1), -1]
    elsewhere: list[object] = list(range(-_QUADRATIC_SUBJECT_SIZE, 0))

    started = time.perf_counter()
    Bag(left).is_subset_of(right)
    with pytest.raises(AssertionFailure):
        Bag(left).is_subset_of(missing)
    Bag(left).does_not_intersect(elsewhere)
    elapsed = time.perf_counter() - started

    assert elapsed < _QUADRATIC_BUDGET_SECONDS, (
        f"membership over {_QUADRATIC_SUBJECT_SIZE} items took {elapsed:.3f}s, past "
        f"the {_QUADRATIC_BUDGET_SECONDS}s budget. `item in some_list` is a scan, so "
        f"asking it once per item is O(n * m) -- see `_searchable`."
    )


# ---------------------------------------------------------------------------
# Two more costs worth bounding
# ---------------------------------------------------------------------------
def test_satisfies_in_any_order_is_polynomial_and_not_factorial() -> None:
    """A pairing in any order is a matching problem, and matching is not a search.

    The worry worth ruling out is that the assertion tries assignments: twelve
    predicates would be 479 million of them. It does not. ``_unmatched_predicate``
    is Kuhn's augmenting-path matching, which visits each item at most once per
    predicate and so evaluates predicates ``O(items * predicates)`` times, with
    ``O(items ** 2 * predicates)`` as the standing worst case -- polynomial either
    way.

    Counted rather than timed, because a count is the same number on every
    machine. The shape below is the awkward one: predicate ``i`` accepts items
    ``0..i``, offered longest-first, so every predicate but the first has to
    displace an owner before it can be placed.

    Measured: 15 evaluations at 5, 36 at 8, 55 at 10, 78 at 12 -- exactly
    ``n * (n + 1) / 2``.
    """
    for size in (5, 8, 10, 12):
        evaluations = 0

        def accepting_up_to(limit: int, /) -> "Callable[[int], bool]":
            def predicate(item: int, /) -> bool:
                nonlocal evaluations
                evaluations += 1
                return item <= limit

            return predicate

        items = list(range(size))
        predicates = [accepting_up_to(limit) for limit in reversed(range(size))]
        Bag(items).satisfies_in_any_order(*predicates)
        assert evaluations <= size**3, (
            f"{size} predicates over {size} items took {evaluations} predicate "
            f"evaluations, past the O(n ** 3) a matching costs. Something is "
            f"searching assignments rather than augmenting a matching."
        )


def test_has_unique_items_still_answers_on_unhashable_items() -> None:
    """A collection of dicts or lists is an ordinary subject, so it is answered.

    It is answered by comparison rather than by hashing, which is quadratic: 800
    unhashable items cost 5.3ms against 51us for 800 hashable ones. That is the
    price of answering at all, and it is the right trade -- but it is a *scan*, so
    a collection of unhashable rows is the one shape of this assertion that does
    not scale.
    """
    Bag([[1], [2], [3]]).has_unique_items()
    with pytest.raises(AssertionFailure) as caught:
        Bag([[1], [2], [1]]).has_unique_items()
    assert "to have unique items" in str(caught.value)


# ---------------------------------------------------------------------------
# One set, one message, however this process hashed it
# ---------------------------------------------------------------------------
#: Enough members to pass the default rendering bound, so the listing is cut and
#: the guard sees which part was kept as well as which item was accused.
_SEEDS: Final = ("0", "1", "2", "7", "42")

_PROBE: Final = """
from lovely_assertions import expect, AssertionFailure

names = {f"user-{letter}" for letter in "abcdefghijklmnop"}
try:
    expect(names).all_equal_to("user-a")
except AssertionFailure as failure:
    print(failure, end="")
"""


def _message_under(seed: str) -> str:
    """The failure message a fresh interpreter produces with that hash seed."""
    import os
    import subprocess
    import sys

    environment = {**os.environ, "PYTHONHASHSEED": seed}
    result = subprocess.run(  # noqa: S603  (our own interpreter, no shell, fixed script)
        [sys.executable, "-c", _PROBE],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
        check=True,
    )
    return result.stdout


def test_a_set_reads_the_same_however_this_process_hashed_it() -> None:
    """A failing set assertion writes one message, not one per interpreter.

    CPython randomises where a string lands in a hash table, per process, so
    walking a set hands the items over in a different order every run. A message
    built from that order accuses a different member each time and -- once the
    listing reaches its bound -- keeps a different part of the collection and
    hides the rest, which means the reader who runs the failing test again to
    look more closely is shown different evidence for the same failure.

    In subprocesses because the seed is chosen before the interpreter starts, so
    this cannot be provoked from inside a running one.
    """
    messages = {seed: _message_under(seed) for seed in _SEEDS}
    distinct = set(messages.values())
    assert len(distinct) == 1, (
        f"the same failing assertion produced {len(distinct)} different messages "
        f"under hash seeds {', '.join(_SEEDS)}:\n"
        + "\n".join(f"  seed {seed}: {text}" for seed, text in messages.items())
    )


def test_the_accused_item_is_the_one_the_listing_shows_first() -> None:
    """The sentence and the listing beside it agree on where to look.

    Ordering the listing without ordering the scan would be worse than neither:
    the message would name an item that the truncated listing need not even
    contain, and the reader would go looking for it among the ones shown.
    """
    message = _message_under("0")
    accused = message.split("but ")[1].split(" did not match")[0]
    listed = message.split("did not match: [")[1]
    assert listed.startswith("'user-a', " + accused), (
        f"the message accuses {accused} but the listing does not reach it first: {message}"
    )


def test_a_predicate_that_changes_its_mind_still_names_what_the_scan_found() -> None:
    """The re-find is a courtesy, not a second verdict.

    The offending item is looked for again in the order the listing beside it
    will use, so the sentence and the listing agree about which item to go
    looking at. But the test for an offence is the caller's own predicate, and
    nothing obliges one to answer the same way twice -- so when the second pass
    turns up nothing, the item the scan actually stopped on is named rather than
    an exception raised out of a half-built failure message.
    """
    answers: list[int] = []

    def only_on_its_first_call(value: int) -> bool:
        answers.append(value)
        return len(answers) == 1

    items = {2, 4, 6}

    with pytest.raises(AssertionFailure) as caught:
        Bag(items).does_not_contain_matching(only_on_its_first_call)

    assert str(caught.value) == (
        "Expected items not to contain an item matching only_on_its_first_call, but 2 did."
    )


# ---------------------------------------------------------------------------
# A bound on the message, not only on how many items it lists
# ---------------------------------------------------------------------------
def test_a_collection_message_bounds_each_item_and_not_only_their_number() -> None:
    """Ten long values is a message, not half a megabyte of one.

    Found by the fuzzer in ``fuzz/properties.py``. ``max_items`` capped how many
    items were listed and nothing capped how large one could be, so a ten-item
    list of fifty-thousand-character values rendered every character of all ten:
    the count was bounded and the message was not.

    The equality path was never affected -- its difference block has always been
    clipped -- which is why this went unnoticed. The assertion everybody reaches
    for was fine; the neighbours that merely *list* a collection were not.
    """
    values = ["x" * 50_000] * 10

    with pytest.raises(AssertionFailure) as caught:
        expect(values).has_length(99)

    message = str(caught.value)
    assert len(message) < 2_000, f"the message ran to {len(message)} characters"
    assert message.startswith("Expected values to have length 99, but had 10: [")
    assert message.endswith("... (49882 more characters)].")


def test_bounding_an_item_does_not_change_an_ordinary_message() -> None:
    """The bound is a ceiling, not a rewrite: short values render as they always did."""
    values = [1, 2, 3]

    with pytest.raises(AssertionFailure) as caught:
        expect(values).has_length(9)

    assert str(caught.value) == "Expected values to have length 9, but had 3: [1, 2, 3]."
