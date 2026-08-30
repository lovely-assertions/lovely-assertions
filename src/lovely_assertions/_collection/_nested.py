"""Assertions about each item, reported together.

The inspector is the caller's, and its failures are collected rather than raised
at the first one -- eight items with three wrong is three lines of report, not
three runs of the test.
"""

from typing import TYPE_CHECKING, Any, Self

from lovely_assertions._collection._base import CollectionBase
from lovely_assertions._collection._comparison import unmatched_predicate
from lovely_assertions._collection._render import render_items
from lovely_assertions._core import collect_failures, describe_predicate
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._text import count_of

if TYPE_CHECKING:
    from collections.abc import Callable, Collection

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class NestedAssertions[E, C: Collection[Any] = Collection[E]](CollectionBase[E, C]):
    """Run an inspector over every item, and collect what it says."""

    __slots__ = ()

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
        unmatched = unmatched_predicate(subject, predicates)
        if unmatched is None:
            return self
        return self._fail(
            f"to satisfy every predicate in any order, but no unclaimed item matched"
            f" {describe_predicate(predicates[unmatched])}"
            f" (predicate {unmatched + 1}): {render_items(subject)}",
            because,
        )
