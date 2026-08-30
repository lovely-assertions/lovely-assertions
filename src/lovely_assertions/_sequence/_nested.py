"""One inspection per item, matched up by position.

Sortable, so it belongs here rather than on the collection subject: the pairing is
positional, and on a subject with no positions it would report findings that
depend on iteration order.
"""

from typing import TYPE_CHECKING, Self

from lovely_assertions._collection import render_items
from lovely_assertions._core import collect_failures
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._sequence._base import SequenceBase
from lovely_assertions._text import count_of

if TYPE_CHECKING:
    from collections.abc import Callable

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class NestedAssertions[E](SequenceBase[E]):
    """Each item against its own inspection, paired by position."""

    __slots__ = ()

    def satisfies_respectively(
        self, *assertions: "Callable[[E], object]", because: str = ""
    ) -> Self:
        """Assert each item satisfies its own inspection, paired by position.

        Sortable, so it belongs here rather than on the collection subject: the
        pairing is by position, and on a subject with no positions it would report
        findings that depend on iteration order. ``all_satisfy`` and
        ``satisfies_in_any_order`` are the order-free forms.

        The sequence has to be exactly as long as the list of inspections; a
        mismatch is reported as such rather than silently checking the shorter of
        the two.
        """
        subject = self._subject
        if len(subject) != len(assertions):
            return self._fail(
                f"to have one item for each of the {count_of(len(assertions), 'assertion')},"
                f" but had {len(subject)}: {render_items(subject)}",
                because,
            )
        collected: list[tuple[int, list[str]]] = []
        for index, item in enumerate(subject):
            failures = collect_failures(assertions[index], item, "satisfies_in_any_order")
            if failures:
                collected.append((index, failures))
        if not collected:
            return self
        return self._fail(
            f"to satisfy its assertions respectively\n{self._findings(collected)}",
            because,
        )
