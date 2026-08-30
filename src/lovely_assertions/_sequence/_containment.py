"""Containment once there are positions to report.

Where an item was found, and the two ordered-subsequence forms -- loose, where
anything may sit between the items, and consecutive, where nothing may. The two
read alike in a test and mean different things about the bug when they fail.
"""

from typing import TYPE_CHECKING, Self, override

from lovely_assertions._collection import render_items
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._sequence._base import SequenceBase
from lovely_assertions._sequence._runs import run_start, subsequence_gap

if TYPE_CHECKING:
    from lovely_assertions._occurrence import Occurrence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

#: Guard for the variadic assertions. A call with nothing to look for either
#: passes whatever the subject is -- a test that asserts nothing -- or could never
#: pass at all. Both are bugs in the test rather than findings about the subject,
#: so they are raised, not reported. The variadics on
#: :class:`~lovely_assertions._string.StringExpect` raise for the same reason.
_NEEDS_VALUES = "at least one value to look for is required"


class ContainmentAssertions[E](SequenceBase[E]):
    """Where an item is, and whether a run of them is."""

    __slots__ = ()

    @override
    def does_not_contain(
        self, item: E, /, *, occurrences: "Occurrence | None" = None, because: str = ""
    ) -> Self:
        """Assert the sequence does not hold ``item``, or not that many times.

        Overrides the inherited assertion for one word of the message: a sequence
        can say *where* it found the item, and ``.index`` is the one lookup an
        unordered collection cannot perform. The test itself is the inherited one,
        ``item in subject``, so the two cannot disagree about the answer.

        A count constraint has nothing to do with position, so that case is handed
        straight back to the collection subject rather than reimplemented here --
        two implementations of one rule is how they come to disagree.
        """
        if occurrences is not None:
            return super().does_not_contain(item, occurrences=occurrences, because=because)
        subject = self._subject
        if item not in subject:
            return self
        return self._fail(
            f"not to contain {format_value(item)}, but found it at index {subject.index(item)}:"
            f" {render_items(subject)}",
            because,
        )

    def contains_in_order(self, *items: E, because: str = "") -> Self:
        """Assert ``items`` all appear, in this order, not necessarily adjacent.

        A subsequence test: anything at all may sit between them, and each wanted
        item consumes a position of its own, so ``contains_in_order("a", "a")``
        needs two ``"a"`` in the subject. Matching is
        ``item is target or item == target``, the rule ``in`` itself applies, so
        this and :meth:`~lovely_assertions._collection.CollectionExpect.contains`
        cannot disagree about whether the sequence holds a value.

        The failure distinguishes an item that is missing entirely from one that
        is present but out of place. Raises ``ValueError`` when called with no
        items -- an assertion with nothing to look for cannot fail, which is a bug
        in the test rather than a finding. :meth:`contains_in_consecutive_order`
        is the strict form that forbids anything in between.
        """
        if not items:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        gap = subsequence_gap(subject, items)
        if gap is None:
            return self
        if gap == 0:
            return self._fail(
                f"to contain {render_items(items)} in order,"
                f" but {format_value(items[0])} was missing from {render_items(subject)}",
                because,
            )
        return self._fail(
            f"to contain {render_items(items)} in order, but {format_value(items[gap])}"
            f" did not appear after {format_value(items[gap - 1])}: {render_items(subject)}",
            because,
        )

    def does_not_contain_in_order(self, *items: E, because: str = "") -> Self:
        """Assert ``items`` do not all appear in this order.

        The negation of :meth:`contains_in_order`, so one item missing or one
        arriving too early is enough; it does not ask for them to be absent.
        :meth:`does_not_contain_in_consecutive_order` is the weaker claim, which
        anything with a gap in it already satisfies. Raises ``ValueError`` when
        called with no items.
        """
        if not items:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        if subsequence_gap(subject, items) is not None:
            return self
        return self._fail(
            f"not to contain {render_items(items)} in order, but it did: {render_items(subject)}",
            because,
        )

    def contains_in_consecutive_order(self, *items: E, because: str = "") -> Self:
        """Assert ``items`` appear as an unbroken run, in this order.

        The run may start at any index; what it may not have is anything in
        between. That is the whole difference from :meth:`contains_in_order`, and
        the failure says which of the two happened -- the items were all there but
        interrupted, or they were not there in that order at all. Raises
        ``ValueError`` when called with no items.
        """
        if not items:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        if run_start(subject, items) is not None:
            return self
        gap = subsequence_gap(subject, items)
        if gap is None:
            return self._fail(
                f"to contain {render_items(items)} in consecutive order,"
                f" but other items came between them: {render_items(subject)}",
                because,
            )
        return self._fail(
            f"to contain {render_items(items)} in consecutive order,"
            f" but {format_value(items[gap])} was not there in that order: {render_items(subject)}",
            because,
        )

    def does_not_contain_in_consecutive_order(self, *items: E, because: str = "") -> Self:
        """Assert ``items`` never appear as an unbroken run in this order.

        Items that all appear in order but with something between them satisfy
        this, which is exactly what separates it from
        :meth:`does_not_contain_in_order`. The failure names the index the run
        started at. Raises ``ValueError`` when called with no items.
        """
        if not items:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        start = run_start(subject, items)
        if start is None:
            return self
        return self._fail(
            f"not to contain {render_items(items)} in consecutive order,"
            f" but they ran from index {start}: {render_items(subject)}",
            because,
        )
