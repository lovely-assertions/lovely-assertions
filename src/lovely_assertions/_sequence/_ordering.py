"""Whether the sequence is in order, and where it stops being.

Both directions, both negated, and all four through one scan. The failure names
the pair that broke the order and the index it broke at, because "not sorted" is
a fact the reader already suspected.
"""

from typing import TYPE_CHECKING, Self

from lovely_assertions._collection import render_items
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._sequence._base import SequenceBase
from lovely_assertions._sequence._order_scan import Sortable, first_out_of_order
from lovely_assertions._sequence._pairs import nan_ordering_note

if TYPE_CHECKING:
    from collections.abc import Callable

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class OrderingAssertions[E](SequenceBase[E]):
    """Sortedness, ascending and descending."""

    __slots__ = ()

    def is_sorted(self, *, key: "Callable[[E], Sortable] | None" = None, because: str = "") -> Self:
        """Assert the items are in non-decreasing order.

        Equal neighbours are in order, and a sequence of fewer than two items is
        sorted -- it holds nothing that could be out of place. ``key`` maps each
        item to the value that is compared, exactly as it does for ``sorted()``,
        and only ``<`` is ever asked of an item or of a ``key`` result.

        A pair that cannot be ordered at all -- a NaN, in practice -- is a failure
        rather than a pass, reported at the index where it breaks the order and
        carrying a note that says why. :meth:`is_sorted_descending` reports the
        same pair, so a sequence holding one cannot satisfy both.
        """
        subject = self._subject
        index = first_out_of_order(subject, key, descending=False)
        if index is None:
            return self
        return self._fail(
            f"to be sorted, but {format_value(subject[index])} at index {index}"
            f" came after {format_value(subject[index - 1])}"
            f"{nan_ordering_note(subject, index, key)}: {render_items(subject)}",
            because,
        )

    def is_not_sorted(
        self, *, key: "Callable[[E], Sortable] | None" = None, because: str = ""
    ) -> Self:
        """Assert some item comes before one it should follow.

        The negation of :meth:`is_sorted`: equal neighbours do not satisfy it, a
        sequence of fewer than two items always fails, and a pair that cannot be
        ordered -- a NaN -- does satisfy it, because it genuinely breaks the
        order. ``key`` behaves as it does there.
        """
        subject = self._subject
        if first_out_of_order(subject, key, descending=False) is not None:
            return self
        return self._fail(f"not to be sorted, but it was: {render_items(subject)}", because)

    def is_sorted_descending(
        self, *, key: "Callable[[E], Sortable] | None" = None, because: str = ""
    ) -> Self:
        """Assert the items are in non-increasing order.

        The mirror of :meth:`is_sorted`, with the same treatment of ``key``, of
        equal neighbours -- in order either way -- of a sequence too short to hold
        a violation, and of a pair that cannot be ordered, which fails here too
        rather than being waved through.
        """
        subject = self._subject
        index = first_out_of_order(subject, key, descending=True)
        if index is None:
            return self
        return self._fail(
            f"to be sorted in descending order, but {format_value(subject[index])} at index {index}"
            f" came after {format_value(subject[index - 1])}"
            f"{nan_ordering_note(subject, index, key)}: {render_items(subject)}",
            because,
        )

    def is_not_sorted_descending(
        self, *, key: "Callable[[E], Sortable] | None" = None, because: str = ""
    ) -> Self:
        """Assert the items are not in non-increasing order.

        The negation of :meth:`is_sorted_descending`, which is not the same claim
        as :meth:`is_sorted`: ``[1, 3, 2]`` is neither ascending nor descending
        and so satisfies this *and* :meth:`is_not_sorted`.
        """
        subject = self._subject
        if first_out_of_order(subject, key, descending=True) is not None:
            return self
        return self._fail(
            f"not to be sorted in descending order, but it was: {render_items(subject)}", because
        )
