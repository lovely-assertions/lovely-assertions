"""Assertions for collections with no order of their own.

``Collection`` gives three things and nothing else: ``__len__``, ``__iter__`` and
``__contains__``. Everything in this module is written to that budget, which is
what lets one subject cover ``set``, ``frozenset``, ``dict.keys()``,
``dict.items()``, ``dict.values()`` and any user collection alongside the lists
and tuples that :class:`~lovely_assertions._sequence.SequenceExpect` refines.

The split is a promise about *meaning*, not a convenience. ``is_sorted`` on a set
is not a slow assertion or an awkward one -- it is a question with no answer, and
the point of a typed assertion library is that such a question is rejected by a
type checker rather than answered at random. So the order-dependent catalogue
lives one class down and is unreachable from here.

Three conventions run through the module.

**Collections in messages go through :func:`render_items`**, which truncates long
ones. A message that pastes ten thousand elements hides the finding instead of
explaining it. How much it prints is the caller's to change -- ``max_items`` in a
:func:`~lovely_assertions._formatting.formatting` block -- because the truncation
that keeps a message readable is exactly what hides the four-hundredth row when
the four-hundredth row is the one being looked for.

**Positions are asked for, never assumed.** A failure inside an unordered
collection has no index to report, so the positional half of a message comes from
:meth:`CollectionExpect._position`, which is empty here and says ``at index N``
in the sequence subject. One implementation, two truthful messages.

**Element-valued parameters are typed ``E``**, not ``object``. ``expect(names)``
should refuse ``contains(3)`` when ``names`` is a ``Collection[str]`` -- an
assertion that can only ever fail is a bug in the test, and catching it before
the suite runs is the point of the typed surface.
"""

from collections.abc import Collection
from typing import TYPE_CHECKING, Any, Self, cast

from lovely_assertions._core import Expect, Found, collect_failures, describe_predicate

# `collect_failures` and `describe_predicate` live in `_core` because
# `Expect.satisfies` needs them too; a second copy here would be a second thing to
# keep in step. They carry no leading underscore precisely so that this import is
# an ordinary one rather than a suppression -- `_core` is already a private module,
# so nothing leaks to the public surface either way.
from lovely_assertions._diff import stable_order
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._formatting import current_formatting
from lovely_assertions._text import clipped, count_of, wildcard_matcher

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence, Sized

    from lovely_assertions._occurrence import Occurrence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

#: `render_items` and `render_or_none` are re-used by `_sequence`, so they carry
#: no leading underscore -- the same reasoning `_core` applies to
#: `collect_failures`. Both modules are private; nothing reaches the public
#: surface either way, and an ordinary import beats a suppression.
__all__ = ["CollectionExpect", "render_items", "render_or_none"]

# How much of a collection a failure prints is not a constant here. Every
# rendering below reads `current_formatting().max_items` *inside its failure
# branch*, so the handful of items that suit a message being skimmed can be
# widened for the one message that is actually being read:
#
#     with formatting(max_items=500):
#         expect(rows).contains(missing)
#
# The default is declared once, in `_formatting`. A passing assertion reaches none
# of this: every read sits past a `return self`, so no assertion pays for a
# ContextVar lookup unless it has already failed.

#: Guard for the variadic assertions. A call with nothing to look for either
#: passes whatever the subject is -- a test that asserts nothing -- or could never
#: pass at all. Both are bugs in the test rather than findings about the subject,
#: so they are raised, not reported. The variadics on
#: :class:`~lovely_assertions._string.StringExpect` raise for the same reason.
_NEEDS_VALUES = "at least one value to look for is required"


class CollectionExpect[E, C: Collection[Any] = Collection[E]](Expect[C]):
    """Assertions that do not depend on order, parameterised by element type.

    ``E`` is the element type. ``C`` is the container, and exists so that
    :class:`~lovely_assertions._sequence.SequenceExpect` can inherit this
    catalogue while keeping ``.subject`` typed as the ``Sequence`` it really has.
    It defaults to ``Collection[E]``, so the subject is written ``CollectionExpect[str]``
    everywhere it is named.

    A user's own subject subclasses it the same way::

        class TagsExpect(CollectionExpect[str]):
            __slots__ = ()
    """

    __slots__ = ()

    # -- message positions -------------------------------------------------
    #
    # Both are **failure path only**, and both are hooks: an inherited assertion
    # reports a position when the subject has one and stays quiet when it does
    # not. Neither may use an f-string -- a failure message is assembled in
    # exactly one place, inside `_fail`, and these only hand it a fragment.
    def _position(self, index: int, /) -> str:
        """The `` at index N`` clause that follows a rendered item.

        Empty here: an item of a set is not *at* anywhere. The sequence subject
        overrides it, which is what puts a real index into every message the
        order-free catalogue produces for an ordered subject.
        """
        _ = index
        return ""

    def _names(self, offends: "Callable[[E], bool]", found: "tuple[int, E]", /) -> str:
        """An offending item and where it sits, as a message names it. Failure path only.

        A method rather than a function so that it reads the subject's own
        ``_position``, which the sequence subject overrides: over an ordered
        subject the clause carries a real index, over a set it carries none.
        """
        index, item = _offender(self._subject, offends, found)
        return format_value(item) + self._position(index)

    def _names_type(self, offends: "Callable[[E], bool]", found: "tuple[int, E]", /) -> str:
        """The same clause, plus the type that made the item an offence. Failure path only."""
        index, item = _offender(self._subject, offends, found)
        return format_value(item) + self._position(index) + " was " + type(item).__name__

    def _finding_tag(self, index: int, /) -> str:
        """The ``at index N: `` tag in front of one nested finding.

        Empty here, for the same reason as :meth:`_position`; the finding itself
        still names the item it came from.
        """
        _ = index
        return ""

    def _findings(self, collected: "list[tuple[int, list[str]]]", /) -> str:
        """Lay out nested failures, one line each, tagged with where they came from.

        Capped at ``max_items`` *items*, for the reason every other collection
        here is capped: a nested inspection over a thousand-element collection
        would otherwise print a thousand lines and bury the finding it exists to
        deliver. The count of items left out is reported, so nothing goes missing
        silently, and a ``formatting(max_items=...)`` block raises the cap when
        the whole list is what the reader needs.
        """
        limit = current_formatting().max_items
        lines: list[str] = []
        for index, failures in collected[:limit]:
            prefix = "  - " + self._finding_tag(index)
            lines.extend(prefix + message.rstrip(".") for message in failures)
        remaining = len(collected) - limit
        if remaining > 0:
            lines.append("  - ... (" + str(remaining) + " more items failed)")
        return "\n".join(lines)

    # -- emptiness ---------------------------------------------------------
    def is_empty(self, *, because: str = "") -> Self:
        """Assert the collection has no items."""
        subject = self._subject
        if len(subject) == 0:
            return self
        return self._fail(f"to be empty, but was {render_items(subject)}", because)

    def is_not_empty(self, *, because: str = "") -> Self:
        """Assert the collection has at least one item."""
        if len(self._subject) > 0:
            return self
        return self._fail("not to be empty, but it was", because)

    def is_none_or_empty(self, *, because: str = "") -> Self:
        """Assert the collection is ``None`` or has no items.

        The subject type excludes ``None``, so a checker will say this can only
        ever be the empty case. The runtime check is real all the same: ``None``
        arrives here through a cast, from untyped code, or from a fixture that
        returned nothing, and absorbing exactly that is what the assertion is for.
        """
        if _is_none_or_empty(self._subject):
            return self
        return self._fail(f"to be None or empty, but was {render_items(self._subject)}", because)

    def is_not_none_or_empty(self, *, because: str = "") -> Self:
        """Assert the collection is neither ``None`` nor empty."""
        if not _is_none_or_empty(self._subject):
            return self
        return self._fail(
            f"not to be None or empty, but was {render_or_none(self._subject)}", because
        )

    # -- length ------------------------------------------------------------
    def has_length(self, expected: int, /, *, because: str = "") -> Self:
        """Assert the collection has exactly ``expected`` items."""
        subject = self._subject
        if len(subject) == expected:
            return self
        return self._fail(
            f"to have length {expected}, but had {len(subject)}: {render_items(subject)}", because
        )

    def does_not_have_length(self, unexpected: int, /, *, because: str = "") -> Self:
        """Assert the collection has any length but ``unexpected``."""
        subject = self._subject
        if len(subject) != unexpected:
            return self
        return self._fail(
            f"not to have length {unexpected}, but was {render_items(subject)}", because
        )

    def has_length_matching(
        self, predicate: "Callable[[int], bool]", /, *, because: str = ""
    ) -> Self:
        """Assert the collection's length satisfies ``predicate``."""
        subject = self._subject
        if predicate(len(subject)):
            return self
        return self._fail(
            f"to have a length matching {describe_predicate(predicate)},"
            f" but had {len(subject)}: {render_items(subject)}",
            because,
        )

    def has_length_greater_than(self, other: int, /, *, because: str = "") -> Self:
        """Assert the collection has more than ``other`` items."""
        subject = self._subject
        if len(subject) > other:
            return self
        return self._fail(
            f"to have more than {count_of(other, 'item')},"
            f" but had {len(subject)}: {render_items(subject)}",
            because,
        )

    def has_length_greater_than_or_equal_to(self, other: int, /, *, because: str = "") -> Self:
        """Assert the collection has at least ``other`` items."""
        subject = self._subject
        if len(subject) >= other:
            return self
        return self._fail(
            f"to have at least {count_of(other, 'item')},"
            f" but had {len(subject)}: {render_items(subject)}",
            because,
        )

    def has_length_less_than(self, other: int, /, *, because: str = "") -> Self:
        """Assert the collection has fewer than ``other`` items."""
        subject = self._subject
        if len(subject) < other:
            return self
        return self._fail(
            f"to have fewer than {count_of(other, 'item')},"
            f" but had {len(subject)}: {render_items(subject)}",
            because,
        )

    def has_length_less_than_or_equal_to(self, other: int, /, *, because: str = "") -> Self:
        """Assert the collection has at most ``other`` items."""
        subject = self._subject
        if len(subject) <= other:
            return self
        return self._fail(
            f"to have at most {count_of(other, 'item')},"
            f" but had {len(subject)}: {render_items(subject)}",
            because,
        )

    def has_same_length_as(self, other: "Collection[object]", /, *, because: str = "") -> Self:
        """Assert the collection is as long as ``other``.

        ``other`` is any collection: comparing a set against a list or against a
        mapping's keys is a fair question, and the element types are nobody's
        business here.
        """
        subject = self._subject
        if len(subject) == len(other):
            return self
        return self._fail(
            f"to have the same length as {render_items(other)},"
            f" but had {count_of(len(subject), 'item')} against {len(other)}",
            because,
        )

    def does_not_have_same_length_as(
        self, other: "Collection[object]", /, *, because: str = ""
    ) -> Self:
        """Assert the collection is not as long as ``other``."""
        subject = self._subject
        if len(subject) != len(other):
            return self
        return self._fail(
            f"not to have the same length as {render_items(other)},"
            f" but both had {count_of(len(subject), 'item')}",
            because,
        )

    # -- containment -------------------------------------------------------
    def contains(
        self, item: E, /, *, occurrences: "Occurrence | None" = None, because: str = ""
    ) -> Self:
        """Assert the collection holds ``item``, and -- with ``occurrences`` -- how often.

            expect(votes).contains("ada", occurrences=exactly(3))

        Without a constraint this is the membership test and nothing else:
        ``item in subject``, answered by the container at the container's own
        cost, which is O(1) on a ``set``.

        With one, the question becomes **how many items equal it**, which no
        container answers on its own, so the collection is walked and every item
        is compared. Three consequences are worth knowing before relying on the
        number.

        *The comparison is* ``x is y or x == y`` -- Python's own membership rule,
        the one ``in`` applies item by item and the one
        :mod:`~lovely_assertions._mapping` writes out at each of its sites.
        Counting any other way would let ``contains(x)`` and ``contains(x,
        occurrences=more_than(0))`` disagree about whether ``x`` is in there at
        all, and two spellings of one question must not have two answers.

        *A value equal to several distinct items counts each of them.* The count
        is of items, not of one object's appearances, so ``contains(1,
        occurrences=once)`` **fails** on ``[1, 1.0, True]``: three distinct items,
        all equal to ``1``, counted three times. ``list.count`` reads it the same
        way.

        *A NaN is counted where it actually is.* ``in`` tests identity before
        equality, so a collection holding a NaN does contain it even though a NaN
        equals nothing, itself included -- and the count follows that same rule
        rather than equality alone. ``contains(nan, occurrences=once)`` therefore
        holds for the list holding *that* NaN and counts zero against a list
        holding a different one, which is exactly what the unconstrained form
        already says about the same two lists.
        """
        subject = self._subject
        if occurrences is None:
            if item in subject:
                return self
            return self._fail(
                f"to contain {format_value(item)}, but was {render_items(subject)}", because
            )
        count = _count_equal(subject, item)
        if occurrences.allows(count):
            return self
        return self._fail(
            f"to contain {format_value(item)} {occurrences.describe()},"
            f" but found {count}: {render_items(subject)}",
            because,
        )

    def does_not_contain(
        self, item: E, /, *, occurrences: "Occurrence | None" = None, because: str = ""
    ) -> Self:
        """Assert the collection does not hold ``item``, or not that many times.

        ``occurrences`` negates the constraint rather than the containment::

            expect(votes).does_not_contain("ada", occurrences=exactly(3))

        passes when "ada" appears twice, four times or not at all, and fails only
        on exactly three. It is the negation of :meth:`contains` with the same
        constraint, which is what makes the pair readable together -- and it
        counts by the same rule, so the two can never disagree about the number.
        """
        subject = self._subject
        if occurrences is None:
            if item not in subject:
                return self
            return self._fail(
                f"not to contain {format_value(item)}, but found it: {render_items(subject)}",
                because,
            )
        count = _count_equal(subject, item)
        if not occurrences.allows(count):
            return self
        return self._fail(
            f"not to contain {format_value(item)} {occurrences.describe()},"
            f" but found {count}: {render_items(subject)}",
            because,
        )

    def contains_single(self, *, because: str = "") -> "Found[Self, E]":
        """Assert the collection holds exactly one item; continue with ``.which``."""
        subject = self._subject
        if len(subject) == 1:
            return Found(self, next(iter(subject)))
        return cast(
            "Found[Self, E]",
            self._fail_narrowing(
                f"to contain a single item, but had {len(subject)}: {render_items(subject)}",
                because,
            ),
        )

    def contains_matching(
        self, predicate: "Callable[[E], bool]", /, *, because: str = ""
    ) -> "Found[Self, E]":
        """Assert some item satisfies ``predicate``; continue on it with ``.which``.

        The "find the row, then assert on it" pattern, in one statement::

            expect(orders).contains_matching(is_refunded).which.is_equal_to(the_late_one)

        Deliberately **not** an overload of :meth:`contains`. A collection whose
        element type is itself a callable would make the overload ambiguous, and
        :meth:`contains` returns ``Self`` -- chains depend on that, and a
        ``Found`` would gain nothing there anyway, since the caller already holds
        the item they searched for. Here they do not: which item matched is the
        answer, which is what earns the continuation.

        The item handed back is the **first** one that matched in iteration
        order. On a subject with no order of its own that is arbitrary but not
        random, and where it matters :meth:`contains_single_matching` is the
        assertion that says so.
        """
        subject = self._subject
        for item in subject:
            if predicate(item):
                return Found(self, item)
        return cast(
            "Found[Self, E]",
            self._fail_narrowing(
                f"to contain an item matching {describe_predicate(predicate)},"
                f" {_nothing_matched(subject)}",
                because,
            ),
        )

    def does_not_contain_matching(
        self, predicate: "Callable[[E], bool]", /, *, because: str = ""
    ) -> Self:
        """Assert no item satisfies ``predicate``.

        The failure names the offending item rather than reporting that one
        exists, and says how many others joined it -- one stray row and a
        systemic problem are different findings, and a message that cannot tell
        them apart sends the reader back to the collection to count by hand.
        """
        subject = self._subject
        for index, item in enumerate(subject):
            if predicate(item):
                return self._fail(
                    f"not to contain an item matching {describe_predicate(predicate)}, but "
                    f"{self._names(predicate, (index, item))} did"
                    f"{_and_the_others(subject, predicate)}",
                    because,
                )
        return self

    def contains_single_matching(
        self, predicate: "Callable[[E], bool]", /, *, because: str = ""
    ) -> "Found[Self, E]":
        """Assert exactly one item satisfies ``predicate``; continue on it with ``.which``.

        The one to reach for when the continuation has to be unambiguous:
        :meth:`contains_matching` hands back whichever item came first, and on an
        unordered subject that is not a claim worth asserting against. Here a
        second match is a failure, so the item that comes back is *the* item.

        The scan stops at the second match; the count in the failure message
        comes from a second pass, on the failure path, where it is free.
        """
        subject = self._subject
        matched = 0
        winner: object = None
        for item in subject:
            if predicate(item):
                matched += 1
                if matched > 1:
                    break
                winner = item
        if matched == 1:
            return Found(self, cast("E", winner))
        if matched == 0:
            return cast(
                "Found[Self, E]",
                self._fail_narrowing(
                    f"to contain exactly one item matching {describe_predicate(predicate)},"
                    f" {_nothing_matched(subject)}",
                    because,
                ),
            )
        accepted = _accepted_by(subject, predicate)
        return cast(
            "Found[Self, E]",
            self._fail_narrowing(
                f"to contain exactly one item matching {describe_predicate(predicate)},"
                f" but {count_of(len(accepted), 'item')} of {len(subject)} matched:"
                f" {render_items(accepted)}",
                because,
            ),
        )

    def only_contains(self, predicate: "Callable[[E], bool]", /, *, because: str = "") -> Self:
        """Assert every item satisfies ``predicate``."""
        subject = self._subject
        for item in subject:
            if not predicate(item):
                return self._fail(
                    f"to contain only items matching {describe_predicate(predicate)},"
                    f" but {render_items(_rejected_by(subject, predicate))} did not",
                    because,
                )
        return self

    def contains_items_of_type(self, expected_type: type[object], /, *, because: str = "") -> Self:
        """Assert every item is an instance of ``expected_type`` -- the FluentAssertions spelling.

        An alias of :meth:`all_are_instance_of`, the way
        :meth:`contains_no_duplicates` is one of :meth:`has_unique_items`. The
        name is this library's spelling of FluentAssertions'
        ``ContainItemsAssignableTo<T>``, and that assertion is about *all* the
        items. Reading the name instead as "holds some items of that type" would
        give a call arriving from FluentAssertions a weaker meaning than the one
        it was written with, and an assertion that passes where the original
        fails is the one bug a library of assertions must not have.
        """
        return self.all_are_instance_of(expected_type, because=because)

    def does_not_contain_items_of_type(
        self, unexpected_type: type[object], /, *, because: str = ""
    ) -> Self:
        """Assert no item is an instance of ``unexpected_type``, subclasses included.

        The mirror of :meth:`contains_items_of_type`, and the negation
        FluentAssertions gives ``NotContainItemsAssignableTo<T>``: *not one* item
        may be of that type. It is not "not all of them are" -- that reading would
        pass on a collection holding a single offender, which is exactly the case
        the assertion is written to catch.

        Unlike its mirror this is a declaration of its own rather than an alias:
        there is no ``none_are_instance_of`` for it to delegate to, and inventing
        a second name for one assertion would only give the reader a choice with
        no consequence.
        """
        subject = self._subject
        for index, item in enumerate(subject):
            if isinstance(item, unexpected_type):
                # `isinstance` narrows `item` to the intersection of `E` and the
                # type asked about, which collapses to `object` while `E` is a
                # type parameter. The cast restates what the loop already knows.
                return self._fail(
                    f"not to contain any item of type {unexpected_type.__name__}, but "
                    f"{
                        self._names_type(
                            lambda v: isinstance(v, unexpected_type), (index, cast('E', item))
                        )
                    }",
                    because,
                )
        return self

    def does_not_contain_none(
        self, *, key: "Callable[[E], object] | None" = None, because: str = ""
    ) -> Self:
        """Assert no item is ``None``, or -- with ``key`` -- that no item *yields* one.

        ``key`` moves the question one level in, which is where it usually
        belongs::

            expect(rows).does_not_contain_none(key=lambda row: row.email)

        asks whether any row is missing an address, not whether the list itself
        holds a ``None`` -- a question about a list of dataclasses that could only
        ever be answered "no". The failure names the key, so the reader is not
        left wondering which of the row's fields was empty.

        Iterates rather than asking ``None in subject``: a ``bytes`` subject holds
        integers and refuses the membership test outright with ``TypeError``, and
        ``bytes`` is a collection this library dispatches to a subject of its own.
        Walking also gives the position, which the membership form could never
        report -- and it is the only form ``key`` could take at all.
        """
        subject = self._subject
        for index, item in enumerate(subject):
            if (item if key is None else key(item)) is None:
                if key is None:
                    return self._fail(
                        f"not to contain None, but found one{self._position(index)}:"
                        f" {render_items(subject)}",
                        because,
                    )
                return self._fail(
                    f"not to contain None under {_describe_key(key)}, but "
                    f"{self._names(lambda v: key(v) is None, (index, item))} gave one:"
                    f" {render_items(subject)}",
                    because,
                )
        return self

    def has_unique_items(
        self, *, key: "Callable[[E], object] | None" = None, because: str = ""
    ) -> Self:
        """Assert no item appears twice, or -- with ``key`` -- no *key* does.

        Vacuous on a ``set``, which is free to say so, and a real question on
        ``dict.values()`` or on any collection built by hand.

        ``key`` is what makes it a real question on a collection of rows::

            expect(orders).has_unique_items(key=lambda order: order.id)

        Two orders with the same id are almost never the same object and almost
        always the bug being looked for, so uniqueness of the whole row would
        report nothing. The failure names **the key's result** -- the id that came
        round twice -- because that is the value the assertion was about; the
        whole row would bury it.
        """
        subject = self._subject
        repeat = _first_repeat(subject, key)
        if repeat is None:
            return self
        value, index = repeat
        return self._fail(
            f"to have unique items{_by_key(key)}, but {format_value(value)}"
            f" appeared again{self._position(index)}: {render_items(subject)}",
            because,
        )

    def contains_no_duplicates(
        self, *, key: "Callable[[E], object] | None" = None, because: str = ""
    ) -> Self:
        """Assert no item appears twice -- the FluentAssertions spelling.

        An alias of :meth:`has_unique_items`, ``key`` included. Both names ship
        because each one reads naturally in a different sentence, and neither is
        worth losing.
        """
        return self.has_unique_items(key=key, because=because)

    # -- set-like relations ------------------------------------------------
    def is_subset_of(self, other: "Collection[E]", /, *, because: str = "") -> Self:
        """Assert every item also appears in ``other``.

        The failure lists the items that were *not* in ``other`` -- the part of
        the subject that made it fail -- rather than printing both collections
        and leaving the difference to the reader.
        """
        subject = self._subject
        if _none_outside(subject, other):
            return self
        return self._fail(
            f"to be a subset of {render_items(other)},"
            f" but also had {render_items(_items_outside(subject, other))}",
            because,
        )

    def is_not_subset_of(self, other: "Collection[E]", /, *, because: str = "") -> Self:
        """Assert at least one item is missing from ``other``.

        An empty collection is a subset of everything, so this fails on one -- and
        says which of the two reasons it was, because "every item was in it" in
        front of an empty collection reads like a bug in the library.
        """
        subject = self._subject
        if not _none_outside(subject, other):
            return self
        if len(subject) == 0:
            return self._fail(
                f"not to be a subset of {render_items(other)}, but it had no items"
                f" -- an empty collection is a subset of anything",
                because,
            )
        return self._fail(
            f"not to be a subset of {render_items(other)}, but every item was in it", because
        )

    def is_superset_of(self, other: "Collection[E]", /, *, because: str = "") -> Self:
        """Assert every item of ``other`` also appears here.

        The mirror of :meth:`is_subset_of`, and read the same way: membership,
        with repeats ignored. A collection is a superset of ``other`` when nothing
        in ``other`` is missing, however many times either side holds it.
        """
        subject = self._subject
        if _none_outside(other, subject):
            return self
        return self._fail(
            f"to be a superset of {render_items(other)},"
            f" but was missing {render_items(_items_outside(other, subject))}",
            because,
        )

    def is_not_superset_of(self, other: "Collection[E]", /, *, because: str = "") -> Self:
        """Assert at least one item of ``other`` is missing here.

        Everything is a superset of an empty collection, so this fails on one --
        and says so, for the reason :meth:`is_not_subset_of` does.
        """
        subject = self._subject
        if not _none_outside(other, subject):
            return self
        if len(other) == 0:
            return self._fail(
                f"not to be a superset of {render_items(other)}, but there was nothing"
                f" it could be missing -- everything is a superset of an empty collection",
                because,
            )
        return self._fail(
            f"not to be a superset of {render_items(other)},"
            f" but it held every item: {render_items(subject)}",
            because,
        )

    def is_proper_subset_of(self, other: "Collection[E]", /, *, because: str = "") -> Self:
        """Assert every item is in ``other``, and ``other`` holds something more.

        "Proper" is the difference between ``<=`` and ``<``: two collections
        holding the same items are subsets of each other and proper subsets of
        neither. The failure says which of the two halves gave way.
        """
        subject = self._subject
        if not _none_outside(subject, other):
            return self._fail(
                f"to be a proper subset of {render_items(other)},"
                f" but also had {render_items(_items_outside(subject, other))}",
                because,
            )
        if _none_outside(other, subject):
            return self._fail(
                f"to be a proper subset of {render_items(other)}, but they held the same items",
                because,
            )
        return self

    def is_proper_superset_of(self, other: "Collection[E]", /, *, because: str = "") -> Self:
        """Assert every item of ``other`` is here, and something else besides."""
        subject = self._subject
        if not _none_outside(other, subject):
            return self._fail(
                f"to be a proper superset of {render_items(other)},"
                f" but was missing {render_items(_items_outside(other, subject))}",
                because,
            )
        if _none_outside(subject, other):
            return self._fail(
                f"to be a proper superset of {render_items(other)}, but they held the same items",
                because,
            )
        return self

    def intersects(self, other: "Collection[E]", /, *, because: str = "") -> Self:
        """Assert the collection shares at least one item with ``other``."""
        subject = self._subject
        if _any_inside(subject, other):
            return self
        return self._fail(
            f"to intersect {render_items(other)}, but shared nothing with {render_items(subject)}",
            because,
        )

    def does_not_intersect(self, other: "Collection[E]", /, *, because: str = "") -> Self:
        """Assert the collection shares no item with ``other``."""
        subject = self._subject
        if not _any_inside(subject, other):
            return self
        return self._fail(
            f"not to intersect {render_items(other)},"
            f" but shared {render_items(_items_inside(subject, other))}",
            because,
        )

    def is_disjoint_from(self, other: "Collection[E]", /, *, because: str = "") -> Self:
        """Assert the collection shares no item with ``other`` -- the set-theory spelling.

        An alias of :meth:`does_not_intersect`, and deliberately not a second
        implementation: two assertions that ask the same question must not be able
        to answer it differently. It reports through the canonical message, the
        way :meth:`contains_no_duplicates` reports through
        :meth:`has_unique_items`.
        """
        return self.does_not_intersect(other, because=because)

    def contains_only(self, *items: E, because: str = "") -> Self:
        """Assert the collection holds exactly ``items`` -- order and repeats ignored.

        Both directions are checked: nothing outside ``items`` may be present, and
        nothing in ``items`` may be missing. That is what "only" means in
        AssertJ's ``containsOnly`` and in this library's own
        :meth:`~lovely_assertions._mapping.MappingExpect.contains_only_keys`, and
        an assertion whose name matches one of those while its behaviour matches
        the other would be a trap.

        The subset-only reading is still available, spelled as what it is::

            expect(statuses).is_subset_of({"ok", "pending"})

        A call with no items asserts the collection is *empty*, which is a real
        assertion rather than a vacuous one -- so, unlike the other variadics
        here, it is allowed (the same exception ``contains_only_keys`` gets).
        """
        subject = self._subject
        if _none_outside(subject, items) and _none_outside(items, subject):
            return self
        missing = _items_outside(items, subject)
        surplus = _items_outside(subject, items)
        if not missing:
            return self._fail(
                f"to contain only {render_items(items)}, but also had {render_items(surplus)}",
                because,
            )
        if not surplus:
            return self._fail(
                f"to contain only {render_items(items)}, but was missing {render_items(missing)}",
                because,
            )
        return self._fail(
            f"to contain only {render_items(items)}, but was missing {render_items(missing)}"
            f" and also had {render_items(surplus)}",
            because,
        )

    def contains_none_of(self, *items: E, because: str = "") -> Self:
        """Assert not one of ``items`` appears in the collection.

        This is the "none of these" half of the multi-item family; there is no
        ``does_not_contain_any``, because it would be this assertion under a
        second name. :meth:`~lovely_assertions._string.StringExpect.does_not_contain_any`
        exists on the string subject, which has no ``contains_none_of``.
        """
        if not items:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        if not _any_inside(items, subject):
            return self
        return self._fail(
            f"not to contain any of {render_items(items)},"
            f" but had {render_items(_items_inside(items, subject))}",
            because,
        )

    # -- multi-item membership ---------------------------------------------
    #
    # The variadic spellings of the set relations just above: `contains_all` asks
    # what `is_superset_of` asks, `contains_any` what `intersects` asks. They ship
    # because the call shape is the difference that matters at a call site --
    # `contains_all("a", "b")` against `is_superset_of({"a", "b"})` -- and because
    # the string subject offers the same names, so a reader who found them there
    # has every reason to expect them here.
    #
    # They are not second implementations. Each one asks its question through the
    # same helper as the relation it mirrors, so the two can differ in wording and
    # cannot differ in the answer.
    def contains_all(self, *items: E, because: str = "") -> Self:
        """Assert every one of ``items`` appears in the collection.

        Extras are allowed: this is containment, not equality. :meth:`contains_only`
        is the assertion that closes the other direction, and
        :meth:`is_superset_of` the one that takes a collection rather than a list
        of arguments.
        """
        if not items:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        if _none_outside(items, subject):
            return self
        return self._fail(
            f"to contain all of {render_items(items)},"
            f" but was missing {render_items(_items_outside(items, subject))}",
            because,
        )

    def does_not_contain_all(self, *items: E, because: str = "") -> Self:
        """Assert at least one of ``items`` is absent.

        The negation of :meth:`contains_all`, so one absence satisfies it.
        :meth:`contains_none_of` is the stricter one, which demands every one of
        them be absent -- the pairing
        :meth:`~lovely_assertions._string.StringExpect.does_not_contain_all` and
        ``does_not_contain_any`` have on the string subject.
        """
        if not items:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        if not _none_outside(items, subject):
            return self
        return self._fail(
            f"not to contain all of {render_items(items)},"
            f" but it held every one of them: {render_items(subject)}",
            because,
        )

    def contains_any(self, *items: E, because: str = "") -> Self:
        """Assert at least one of ``items`` appears in the collection."""
        if not items:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        if _any_inside(items, subject):
            return self
        return self._fail(
            f"to contain at least one of {render_items(items)}, but was {render_items(subject)}",
            because,
        )

    # -- element types -----------------------------------------------------
    def all_are_instance_of(self, expected_type: type[object], /, *, because: str = "") -> Self:
        """Assert every item is an instance of ``expected_type``, subclasses included."""
        subject = self._subject
        for index, item in enumerate(subject):
            if not isinstance(item, expected_type):
                return self._fail(
                    f"to contain only instances of {expected_type.__name__}, but "
                    f"{
                        self._names_type(lambda v: not isinstance(v, expected_type), (index, item))
                    }",
                    because,
                )
        return self

    def all_are_exactly_type(self, expected_type: type[object], /, *, because: str = "") -> Self:
        """Assert every item is exactly ``expected_type`` -- a subclass does not count."""
        subject = self._subject
        for index, item in enumerate(subject):
            if type(item) is not expected_type:
                return self._fail(
                    f"to contain only {expected_type.__name__} exactly, but "
                    f"{self._names_type(lambda v: type(v) is not expected_type, (index, item))}",
                    because,
                )
        return self

    def all_equal_to(self, value: E, /, *, because: str = "") -> Self:
        """Assert every item equals ``value``."""
        subject = self._subject
        for index, item in enumerate(subject):
            if item != value:
                return self._fail(
                    f"to contain only {format_value(value)}, but "
                    f"{self._names(lambda v: v != value, (index, item))}"
                    f" did not match: {render_items(subject)}",
                    because,
                )
        return self

    # -- nested assertions -------------------------------------------------
    def all_satisfy(self, action: "Callable[[E], object]", /, *, because: str = "") -> Self:
        """Assert every item satisfies the nested assertions in ``action``.

        Failures inside ``action`` are collected rather than raised one at a
        time, so one call reports every item that was wrong and -- where the
        subject has positions -- says which one each finding came from. A
        non-assertion exception still propagates: a broken inspector is a bug in
        the test, not a finding about the subject.
        """
        collected: list[tuple[int, list[str]]] = []
        for index, item in enumerate(self._subject):
            failures = collect_failures(action, item, "only_contains")
            if failures:
                collected.append((index, failures))
        if not collected:
            return self
        return self._fail(
            f"to satisfy the inspection for every item\n{self._findings(collected)}",
            because,
        )

    def satisfies_in_any_order(self, *predicates: "Callable[[E], bool]", because: str = "") -> Self:
        """Assert each predicate holds for a *distinct* item, in any order.

        The collection has to be exactly as long as the list of predicates, and
        the pairing has to be one-to-one: with items ``[1, 2]`` and predicates
        ``is_one_or_two, is_one``, matching each predicate independently would
        pass, and it would be wrong -- ``is_one_or_two`` has taken the only item
        ``is_one`` can use. The assignment is solved as a matching instead, so a
        predicate gives an item back whenever it has somewhere else to go.

        A call with no predicates asserts the collection is empty. The failure
        names the first predicate that no unclaimed item could satisfy, together
        with its position in the argument list.
        """
        subject = self._subject
        if len(subject) != len(predicates):
            return self._fail(
                f"to have one item for each of the {count_of(len(predicates), 'predicate')},"
                f" but had {len(subject)}: {render_items(subject)}",
                because,
            )
        unmatched = _unmatched_predicate(subject, predicates)
        if unmatched is None:
            return self
        return self._fail(
            f"to satisfy every predicate in any order, but no unclaimed item matched"
            f" {describe_predicate(predicates[unmatched])}"
            f" (predicate {unmatched + 1}): {render_items(subject)}",
            because,
        )

    # -- wildcard matching (string collections) ----------------------------
    def contains_match[S: "CollectionExpect[str]"](
        self: S, pattern: str, /, *, because: str = ""
    ) -> S:
        """Assert some item matches the wildcard ``pattern`` (``*`` and ``?``).

        Offered only on collections of strings: the self-type is the constraint, so
        ``expect({1, 2}).contains_match("a*")`` is a type error rather than a
        ``TypeError`` at runtime. ``Self`` cannot be written alongside an explicit
        ``self`` annotation -- both checkers reject that -- so the constraint is
        carried by a type variable *bound* to ``CollectionExpect[str]`` instead,
        which is the same promise: a subclass gets its own type back, and a
        collection of anything else cannot call the method at all.
        """
        subject = self._subject
        matcher = wildcard_matcher(pattern, ignoring_case=False)
        for item in subject:
            if matcher.fullmatch(item) is not None:
                return self
        return self._fail(
            f"to contain a match for {format_value(pattern)}, but was {render_items(subject)}",
            because,
        )

    def does_not_contain_match[S: "CollectionExpect[str]"](
        self: S, pattern: str, /, *, because: str = ""
    ) -> S:
        """Assert no item matches the wildcard ``pattern`` (``*`` and ``?``)."""
        subject = self._subject
        matcher = wildcard_matcher(pattern, ignoring_case=False)
        for index, item in enumerate(subject):
            if matcher.fullmatch(item) is not None:
                return self._fail(
                    f"not to contain a match for {format_value(pattern)}, but "
                    f"{self._names(lambda v: matcher.fullmatch(v) is not None, (index, item))}"
                    f" matched",
                    because,
                )
        return self

    # -- projection --------------------------------------------------------
    def _carrying_name[D: "Expect[Any]"](self, derived: D, /) -> D:
        """Hand an explicit subject name on to a subject derived from this one.

        A derived wrapper is a new object and has no name, so a failure reported
        against it falls back to reading the source line -- which finds
        ``expect(rows)`` and is right often enough. It is wrong in exactly the two
        places :meth:`~lovely_assertions._core.Expect.described_as` exists to fix:
        a loop, where every iteration names the same variable, and a helper, where
        the line names the parameter rather than the caller's value. An explicit
        name has to survive at least as well as a recovered one, or naming the
        subject stops being worth doing.

        Not the failure path -- but not an assertion's happy path either: nothing
        calls this except a transformation that is already materialising a list.
        """
        name = getattr(self, "_name", None)
        return derived if name is None else derived.described_as(name)

    def extracting[R](self, selector: "Callable[[E], R]", /) -> "CollectionExpect[R]":
        """Assert about one field of every item instead of about the items.

        assertpy's most-loved feature, typed::

            expect(orders).extracting(lambda order: order.customer).contains_only("ana")

        **The callable form only.** ``extracting("customer")`` is the spelling
        assertpy is known for and it cannot be typed: a checker cannot know that
        the attribute exists, and it certainly cannot know what type it has, so
        every assertion downstream of the string form would be checked against
        ``Any`` -- an autocomplete list that is empty and a type error that never
        fires. The callable survives a rename, and ``R`` is inferred from it, so
        the returned subject carries a real element type.

        This is a transformation, not an assertion: it makes no claim, so it
        cannot fail and takes no ``because``. A selector that raises propagates,
        the way a broken inspector does -- that is a bug in the test rather than a
        finding about the subject.

        **The result is a collection, not a sequence**, and that is the whole
        design. Extraction materialises a list, so returning a
        ``SequenceExpect`` would type-check and would be a trap: the order of that
        list is the *source's* iteration order, and a ``set`` has none worth
        asserting about. ``expect(tags).extracting(len).is_sorted()`` would then
        compile and pass or fail on hash order.
        :class:`~lovely_assertions._sequence.SequenceExpect` overrides this to
        return a sequence subject, which is where the ordered catalogue is
        honestly available -- the same split, one level down.

        A name given with ``described_as`` or ``expect(..., name=...)`` carries
        over; see :meth:`_carrying_name`.
        """
        extracted: CollectionExpect[R] = CollectionExpect(
            [selector(item) for item in self._subject]
        )
        return self._carrying_name(extracted)


# ---------------------------------------------------------------------------
# Rendering helpers -- failure path only.
#
# None of them may use an f-string: an f-string is a message, and a message is
# built in exactly one place, inside `_fail`. They concatenate and join instead,
# so that a helper reached from an argument list cannot format eagerly.
# ---------------------------------------------------------------------------
#: Brackets per container kind, so a tuple still looks like a tuple and a set
#: like a set even though the items are rendered one at a time.
_BRACKETS: dict[type[object], tuple[str, str]] = {
    list: ("[", "]"),
    tuple: ("(", ")"),
    set: ("{", "}"),
    frozenset: ("frozenset({", "})"),
}

#: How an *empty* container of each kind reads. Python renders these itself and
#: they are worth copying: a set has no empty literal, so composing the brackets
#: above would print `{}`, which is a dict.
_EMPTY_RENDERING: dict[type[object], str] = {
    list: "[]",
    tuple: "()",
    set: "set()",
    frozenset: "frozenset()",
}


def in_message_order[T](items: "Collection[T]", /) -> "Collection[T]":
    """The order a failure message reads ``items`` in. Failure path only.

    A set has no order of its own, and CPython walks one in hash order, which is
    randomised per process. Left alone, two runs of the same failing assertion
    name a different item and -- once the listing is cut to its bound -- hide a
    different part of the collection, so a reader who runs it a second time to
    look closer is shown different evidence. Sorting where there was no order to
    lose makes the message the same every time.

    A sequence keeps the order it arrived in, because there the order *is* the
    finding: which item sits where is what the message is about.
    """
    if isinstance(items, set | frozenset):
        return stable_order(list(items))
    return items


def _offender[T](
    items: "Collection[T]", offends: "Callable[[T], bool]", found: "tuple[int, T]", /
) -> "tuple[int, T]":
    """The item a message should name, and where it sits. Failure path only.

    The scan that decided the verdict stopped at whatever the container handed
    over first, and for a set that is an order which changes between runs. This
    re-finds the offender in the order the message will *list* the items in, so
    the item the sentence accuses is the one the reader meets first in the
    listing beside it. Over a sequence the two orders are the same, and this
    gives back exactly what the scan already found.

    ``found`` is that result, returned unchanged if the second pass disagrees:
    the test for an offence is often the caller's own predicate, which is under
    no obligation to answer the same way twice, and naming the item the scan
    stopped on beats raising out of a half-built failure message.
    """
    for index, item in enumerate(in_message_order(items)):
        if offends(item):
            return index, item
    return found


def render_items(items: "Collection[object]", /) -> str:
    """Render a collection for a failure message, truncating a long one.

    Items are rendered one at a time rather than through the collection's own
    ``repr``, because a container's ``repr`` calls each item's ``__repr__``
    directly and a registered formatter would never be consulted -- which would
    make formatters useless for exactly the case they are wanted in,
    ``expect(orders).contains(order)``. The brackets are restored from the
    container's type so the rendering still reads as what it is.

    Past ``current_formatting().max_items`` the listing is cut and says how many
    it left out. That bound is read here rather than baked in, so a
    ``formatting(max_items=...)`` block changes what every collection message in
    the library prints -- this function renders them all, the sequence subject
    included. The read is safe because nothing calls this except a message being
    built: **failure path only**, so a passing assertion never touches the
    ContextVar behind it.
    """
    total = len(items)
    if total == 0:
        return _EMPTY_RENDERING.get(type(items), "[]")
    options = current_formatting()
    limit = options.max_items
    opening, closing = _BRACKETS.get(type(items), ("[", "]"))
    shown: list[str] = []
    for item in in_message_order(items):
        if len(shown) == limit:
            break
        # Each item, not just how many of them. Bounding the count alone leaves
        # the message as large as the values in it -- ten items whose renderings
        # run to fifty thousand characters each is half a megabyte of message,
        # which is the thing this bound exists to prevent.
        shown.append(clipped(format_value(item), options.max_chars))
    body = ", ".join(shown)
    if total <= limit:
        if total == 1 and opening == "(":
            return "(" + body + ",)"
        return opening + body + closing
    return "[" + body + ", ... (" + str(total - limit) + " more)]"


def render_or_none(subject: "Collection[object] | None", /) -> str:
    """Render a collection, or ``None`` for a subject that turned out to be missing.

    Declared as an optional parameter for the reason ``_is_none_or_empty`` is:
    the subject type excludes ``None``, so the comparison would be flagged as
    unreachable if it were written inside the assertion.
    """
    if subject is None:
        return "None"
    return render_items(subject)


def _items_outside(items: "Collection[object]", container: "Collection[object]", /) -> list[object]:
    """The items that are not in ``container``. Failure path only.

    Through :func:`_searchable` for the reason :func:`_none_outside` is. This one
    runs only once an assertion has already failed, so its *allocation* is free --
    but its cost is not, and it is a half a reader really does wait on: the scan
    that decided the verdict stopped at the first item outside, and this walks
    every one of them. Over two long collections that second pass is most of what
    a failing set relation takes, which is why it too goes through the hash table
    rather than falling back to a quadratic scan.
    """
    holder = _searchable(items, container)
    return [item for item in items if item not in holder]


def _items_inside(items: "Collection[object]", container: "Collection[object]", /) -> list[object]:
    """The items that are in ``container``. Failure path only."""
    holder = _searchable(items, container)
    return [item for item in items if item in holder]


def _rejected_by(items: "Collection[Any]", predicate: "Callable[[Any], bool]", /) -> list[object]:
    """Every item the predicate turned down.

    Re-runs the predicate over the whole collection, which is fine: this is the
    failure path, and the alternative -- collecting rejects as we go -- would
    make every *passing* call allocate a list it throws away.
    """
    return [item for item in items if not predicate(item)]


def _accepted_by(items: "Collection[Any]", predicate: "Callable[[Any], bool]", /) -> list[object]:
    """Every item the predicate accepted. The mirror of :func:`_rejected_by`."""
    return [item for item in items if predicate(item)]


def _nothing_matched(items: "Collection[object]", /) -> str:
    """The ``but ...`` half of a message for a predicate not one item satisfied.

    "no item matched" is no use on a five-hundred-row collection: it does not say
    whether five hundred items were checked or none were. So this reports the
    number actually examined and shows a bounded sample of them, and treats the
    empty collection as the separate finding it is -- "checked 0 items" in front
    of ``[]`` reads like a bug in the library.
    """
    total = len(items)
    if total == 0:
        return "but it was empty"
    return "but checked " + count_of(total, "item") + " and none matched: " + render_items(items)


def _and_the_others(items: "Collection[Any]", predicate: "Callable[[Any], bool]", /) -> str:
    """The ``(and so did N other items)`` tail, or ``""`` when the match was alone.

    One stray row and a systemic problem are different findings. Counting the
    rest costs a second pass over the collection, which is free here: nothing
    calls this unless an assertion has already failed.
    """
    others = sum(1 for item in items if predicate(item)) - 1
    if others <= 0:
        return ""
    return " (and so did " + count_of(others, "other item") + ")"


def _describe_key(key: "Callable[[Any], object]", /) -> str:
    """Name a ``key=`` function for a failure message. Failure path only.

    ``describe_predicate`` in ``_core`` applies the same rule and would be the
    obvious call, except for its fallback: an anonymous *key* is not "the
    predicate", and a message that calls it one sends the reader looking for a
    predicate that is not in the call. The shared half is a single ``getattr``;
    the noun is the whole difference, and it is the part that gets read.
    """
    name = getattr(key, "__name__", None)
    if isinstance(name, str) and name != "<lambda>":
        return name
    return "the key"


def _by_key(key: "Callable[[Any], object] | None", /) -> str:
    """The `` by <key>`` clause a keyed uniqueness failure carries, or ``""``."""
    if key is None:
        return ""
    return " by " + _describe_key(key)


# ---------------------------------------------------------------------------
# Comparison helpers -- these run on the happy path, so they allocate nothing
# beyond what the question itself requires.
# ---------------------------------------------------------------------------
def _is_none_or_empty(subject: "Sized | None", /) -> bool:
    """Whether the subject is missing entirely or simply holds nothing.

    Declared as an optional parameter so the ``None`` branch is honest to both
    checkers: ``CollectionExpect``'s subject type excludes ``None``, and a
    comparison against it inside the method would be flagged as unreachable.
    """
    return subject is None or len(subject) == 0


def _count_equal(candidates: "Collection[Any]", value: object, /) -> int:
    """How many of ``candidates`` count as ``value``. Runs whether or not it fails.

    ``x is y or x == y``, Python's own membership rule -- the comparison ``in``
    makes item by item, and the one ``_mapping`` spells out at each of its sites
    for the same reason: equality alone would report a NaN a collection
    demonstrably holds as absent, so an occurrence count and a plain ``contains``
    would answer one question two ways.

    Spelled as a loop rather than ``sum(1 for ...)``: the generator expression is
    an allocation, and this runs on the *passing* side of every occurrence-
    constrained assertion, which is required to allocate nothing. Walking is also
    the only implementation available -- ``__contains__`` answers whether, never
    how many -- so a ``set`` pays a scan here where an unconstrained ``contains``
    pays a hash lookup.
    """
    count = 0
    for candidate in candidates:
        if candidate is value or candidate == value:
            count += 1
    return count


#: Container kinds whose ``__contains__`` is a scan, *exactly* -- a subclass may
#: override it, and then a scan is not what it does. ``set``, ``frozenset``,
#: ``range`` and ``dict.keys()`` are absent for the opposite reason: they already
#: answer in constant time, so hashing them a second time would be pure loss.
#:
#: ``dict.values()`` is here and is the surprising member. Its two sibling views
#: are not: ``keys`` is the dictionary's own lookup, and ``items`` is that lookup
#: followed by one comparison. ``values`` has no index at all and walks, so a
#: membership test against a large dictionary's values costs orders of magnitude
#: more than the same test against its keys. It is also the view a mapping subject
#: reaches for, so it is a real collection subject and not a curiosity. Named
#: through ``type(...)`` rather than by importing it, because ``dict_values`` is
#: exported from nowhere and reaching ``types`` for it would be a module-level
#: import bought for one frozenset literal. The empty mapping is annotated only so
#: that a strict checker gets a type parameter for it: ``type({}.values())`` on a
#: bare literal is partially unknown.
_NO_ENTRIES: "dict[object, object]" = {}
_SCANNED_LINEARLY: "frozenset[type[object]]" = frozenset({list, tuple, type(_NO_ENTRIES.values())})

#: Types whose ``__hash__`` and ``__eq__`` are known to agree. *Exactly* these
#: types and not their subclasses, because a subclass may override either one and
#: then nothing is known about the pair again.
#:
#: Small on purpose. Every builtin here is one whose equality is settled by value
#: and whose hash is derived from that same value, the numeric tower included --
#: ``1 == 1.0 == True`` and all three hash to 1, ``0.0 == -0.0`` and both hash to
#: 0. ``datetime``, ``Decimal``, ``UUID`` and ``Enum`` would all qualify and none
#: of them is here: naming them means importing them, and importing this package
#: must not drag in a module that a question about a list of strings has no use
#: for. Their collections take the scan instead.
_HASH_SAFE: "frozenset[type[object]]" = frozenset(
    {bool, bytes, complex, float, int, str, type(None)}
)

#: The three things that must all be true before a hash table is worth building.
#:
#: The container must be long enough to cover the fixed cost of building at all
#: (:data:`_HASHING_PAYS_FROM`), and enough lookups must be coming to amortise it
#: (:data:`_REPEATED_LOOKUPS_FROM`) -- ``contains_any("x")`` against a
#: hundred-thousand-item list is a *single* lookup, and hashing the whole list to
#: answer it is slower than the scan it replaces.
#:
#: The third is the one that is genuinely easy to get wrong. Building costs a hash
#: plus a type check per item of the container, both of which have to walk it, so
#: the decision is ``O(n)`` **whatever it decides**. A scan does *not* cost
#: ``O(n)`` per lookup. It costs one comparison per item it passes before it finds
#: what it is looking for, and stops. So the scan's price turns on where the
#: needles *are*, not merely on how many there are, and the worst case is the only
#: case in which "both sides are linear in n and it cancels" is true.
#:
#: The shape that makes the point: a handful of needles that all sit at the front
#: of a very long list. The scan answers in microseconds and hashing the list takes
#: milliseconds -- orders of magnitude slower, to answer the same question, on a
#: shape nobody would call exotic, since an early slice of a sorted collection is
#: exactly that. Unbounded, too: the ratio grows with the container.
#:
#: No floor on the lookup count alone can bound that, because the best case a scan
#: can have costs ``O(m)`` however large ``m`` is. What bounds it is requiring the
#: container to be no more than :data:`_LONGEST_CONTAINER_PER_LOOKUP` times the
#: lookup count, which caps the loss at roughly that ratio's worth against a best
#: case that was already microseconds, while keeping every win the table was built
#: for. Those wins are all shaped ``m ~ n`` -- two long lists compared item for
#: item, a mapping's values against another mapping's keys -- and they sail
#: through, turning tens of seconds into milliseconds.
#:
#: What the gate still costs where it opens too eagerly, stated rather than
#: hidden: at exactly the two floors, with hashable integers on both sides, the
#: scan is marginally faster than the table built to replace it -- a single-digit
#: percentage, paid on the smallest collection the gate ever opens for.
_HASHING_PAYS_FROM = 32
_REPEATED_LOOKUPS_FROM = 16
_LONGEST_CONTAINER_PER_LOOKUP = 8


def _searchable(
    items: "Collection[object]", container: "Collection[object]", /
) -> "Collection[object]":
    """``container``, or a set that answers ``in`` for it *identically* and faster.

    ``item in some_list`` is a scan, so asking it once per item turns every
    set-like relation in this module into ``O(n * m)`` -- two long lists compared
    against each other take tens of seconds. Hashing the container once and asking
    the hash table instead brings the same comparison down to milliseconds.

    It is also, in general, **a different question**, which is why this returns
    the container unchanged far more often than it returns a set.

    *What a set does not change.* Identity survives it. ``in`` compares
    ``x is y or x == y`` item by item, and a set does the same inside the bucket
    it lands in -- CPython compares the stored pointer before it compares the
    objects. So the NaN case that this module spells out at eight sites is safe:
    a collection holding a NaN contains *that* NaN either way, because the lookup
    hashes the very object that is stored and lands in its bucket. Two distinct
    NaNs are absent from each other either way, for the matching reason -- a float
    NaN hashes by identity, so they do not even share a bucket.

    *What a set does change*, and it is not academic:

    * **A type whose hash disagrees with its equality.** Value equality with an
      identity hash is the standard ORM row: ``a == b`` is true and
      ``hash(a) != hash(b)``, so ``b in [a]`` finds it and ``b in {a}`` does not.
      Python documents that pair as an invariant, and the types that break it
      break it deliberately.
    * **A needle the container's own type would never have matched.** Membership
      compares ``element == needle`` with the reflected fallback, so an object
      with a permissive ``__eq__`` is found in a list of strings and is not found
      in a set of them.
    * **An unhashable needle.** ``["x"] in ["a"]`` is ``False``; ``["x"] in {"a"}``
      is a ``TypeError``.

    So the gate is on **types, on both sides**, rather than on a ``try`` around
    the build. Catching ``TypeError`` would cover only the third of those three --
    the two that return a *wrong answer* instead of raising are exactly the two it
    cannot see, and they are the ones that matter.

    That check walks the container, so it is ``O(n)`` and it is spent *before* the
    answer is known -- twice the cost of the ``set`` it is deciding about, and paid
    in full on a container that turns out to hold a ``Decimal`` in its last slot.
    That is the reason the length gate is not the only gate: see
    :data:`_LONGEST_CONTAINER_PER_LOOKUP`, which is what keeps an ``O(n)`` decision
    from being taken on behalf of a handful of lookups that a scan would have
    answered in microseconds.

    The cost of that strictness is stated rather than hidden: a collection of
    dataclasses, ``Decimal`` or ``datetime`` keeps the quadratic scan even though
    its hashing is perfectly well behaved. That is the trade this module makes
    everywhere -- a right answer slowly beats a wrong one quickly -- and the way
    out is to widen :data:`_HASH_SAFE` with a type whose contract can be *read*,
    never to guess from behaviour.

    Returns the container itself rather than ``None`` for "scan it", so that every
    caller is one loop over one name and the two paths cannot drift into two
    answers. What that shape costs the small case is a call, two ``len`` and two
    comparisons -- a measurable fraction of a three-item relation, and the guards
    are ordered cheapest first so that a small collection is only ever charged
    those. Writing the gate out at each call site instead buys back about half of
    that and puts the decision about what ``in`` means in several places rather
    than one.
    """
    held = len(container)
    lookups = len(items)
    if held < _HASHING_PAYS_FROM or lookups < _REPEATED_LOOKUPS_FROM:
        return container
    if lookups * _LONGEST_CONTAINER_PER_LOOKUP < held:
        return container
    if type(container) not in _SCANNED_LINEARLY:
        return container
    for item in container:
        if type(item) not in _HASH_SAFE:
            return container
    for item in items:
        if type(item) not in _HASH_SAFE:
            return container
    return set(container)


def _none_outside(items: "Collection[object]", container: "Collection[object]", /) -> bool:
    """Whether every one of ``items`` is in ``container``.

    Spelled as a loop rather than ``all(item in holder for item in items)``
    because this runs on the happy path: the generator expression the tidier
    spelling needs is an allocation on every *passing* assertion, and a passing
    assertion is required to allocate nothing at all.

    :func:`_searchable` decides whether the membership test is answered by a scan
    or by a hash table, and answers the same question either way -- see its
    docstring for what "the same question" is doing there, because a set is not a
    drop-in for ``in`` and the cases where it is not are the interesting ones.
    """
    holder = _searchable(items, container)
    for item in items:  # noqa: SIM110  (a generator expression would allocate)
        if item not in holder:
            return False
    return True


def _any_inside(items: "Collection[object]", container: "Collection[object]", /) -> bool:
    """Whether at least one of ``items`` is in ``container``.

    Spelled as a loop rather than ``any(item in holder for item in items)``
    for the reason :func:`_none_outside` is: the generator expression is an
    allocation on every *passing* assertion, and those must allocate nothing.

    One helper serves both call shapes -- ``intersects(other)`` and
    ``contains_any(*items)`` ask the same question of the same two collections --
    so the two assertions can word their failures differently and cannot disagree
    about the answer.

    Through :func:`_searchable`, like its mirror. The table is built up front even
    though this can return on the first item, which is the right way round: the
    call that returns early is the *cheap* one, and the call that has to look at
    everything -- ``does_not_intersect`` over two long lists, which succeeds only
    by finding nothing -- is the one that would otherwise be quadratic.
    """
    holder = _searchable(items, container)
    for item in items:  # noqa: SIM110  (a generator expression would allocate)
        if item in holder:
            return True
    return False


def _first_repeat(
    items: "Collection[Any]", key: "Callable[[Any], object] | None" = None, /
) -> tuple[object, int] | None:
    """The first value that has already been seen, with where it was, or ``None``.

    The *value* is the item itself, or what ``key`` makes of it -- which is what
    a keyed failure has to name, since the two rows that collided are different
    objects and only their ids are the finding.

    Hashable values go through a ``set``; the moment one is not hashable the scan
    falls back to a linear comparison for it, because a collection of dicts is an
    ordinary test subject and refusing to check it would be worse than being slow.

    The value comes back alongside its position because an unordered subject
    cannot be asked for it afterwards -- there is no ``items[index]`` to go back
    to.
    """
    seen: set[object] = set()
    unhashable: list[object] = []
    for index, item in enumerate(items):
        value = item if key is None else key(item)
        try:
            if value in seen:
                return value, index
            seen.add(value)
        except TypeError:
            if value in unhashable:
                return value, index
            unhashable.append(value)
    return None


def _unmatched_predicate(
    items: "Collection[Any]", predicates: "Sequence[Callable[[Any], bool]]", /
) -> int | None:
    """Index of the first predicate no *distinct* item can be assigned to.

    Kuhn's augmenting-path matching, not one ``any()`` per predicate: given items
    ``[1, 2]`` and predicates ``is_one_or_two, is_one``, the independent test
    passes both and the assignment is still impossible -- ``is_one_or_two`` has
    taken the only item ``is_one`` can use. Augmenting lets it hand that item
    back when it has somewhere else to go.
    """
    owner: list[int | None] = [None] * len(items)
    for index in range(len(predicates)):
        if not _augment(index, items, predicates, owner, [False] * len(items)):
            return index
    return None


def _augment(
    predicate: int,
    items: "Collection[Any]",
    predicates: "Sequence[Callable[[Any], bool]]",
    owner: "list[int | None]",
    visited: "list[bool]",
    /,
) -> bool:
    """Find an item for ``predicate``, displacing owners that have somewhere to go."""
    test = predicates[predicate]
    for index, item in enumerate(items):
        if visited[index] or not test(item):
            continue
        visited[index] = True
        holder = owner[index]
        if holder is None or _augment(holder, items, predicates, owner, visited):
            owner[index] = predicate
            return True
    return False
