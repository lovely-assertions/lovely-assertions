"""One value, present or absent, and the single-item case.

``contains_single`` is not ``has_length(1)`` plus ``contains``: it says what the
one item *is* when there is exactly one, and says how many there were when there
is not.
"""

from typing import TYPE_CHECKING, Any, Self, cast

from lovely_assertions._collection._base import CollectionBase
from lovely_assertions._collection._comparison import count_equal
from lovely_assertions._collection._render import render_items
from lovely_assertions._core import Found
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value

if TYPE_CHECKING:
    from collections.abc import Collection

    from lovely_assertions._occurrence import Occurrence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class ContainmentAssertions[E, C: Collection[Any] = Collection[E]](CollectionBase[E, C]):
    """Is this value in there, and how many times."""

    __slots__ = ()

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
        count = count_equal(subject, item)
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
        count = count_equal(subject, item)
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
