"""Membership decided by a callback rather than by equality.

The failure has to say more than "nothing matched", because the caller wrote the
predicate and cannot see what it was asked about. Each of these names a sample of
what was screened and how much of it there was.
"""

from typing import TYPE_CHECKING, Any, Self, cast

from lovely_assertions._collection._base import CollectionBase
from lovely_assertions._collection._clauses import (
    accepted_by,
    and_the_others,
    nothing_matched,
    rejected_by,
)
from lovely_assertions._collection._render import render_items
from lovely_assertions._core import Found, describe_predicate
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._text import count_of

if TYPE_CHECKING:
    from collections.abc import Callable, Collection

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class PredicateAssertions[E, C: Collection[Any] = Collection[E]](CollectionBase[E, C]):
    """Which item satisfies a predicate the caller wrote."""

    __slots__ = ()

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
                f" {nothing_matched(subject)}",
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
                    f"{and_the_others(subject, predicate)}",
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
                    f" {nothing_matched(subject)}",
                    because,
                ),
            )
        accepted = accepted_by(subject, predicate)
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
                    f" but {render_items(rejected_by(subject, predicate))} did not",
                    because,
                )
        return self
