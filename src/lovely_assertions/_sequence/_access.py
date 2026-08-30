"""One item, by index, and the subject it becomes.

The continuation is the point: ``.which`` re-dispatches on what was stored, so a
list of strings gives a string subject and the whole string catalogue with it.
"""

from typing import Self, cast

from lovely_assertions._collection import render_items
from lovely_assertions._core import Found
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._sequence._base import SequenceBase

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class AccessAssertions[E](SequenceBase[E]):
    """Reading one item out, and continuing on it."""

    __slots__ = ()

    def has_element_at(self, index: int, value: E, /, *, because: str = "") -> "Found[Self, E]":
        """Assert the item at ``index`` equals ``value``; continue with ``.which``.

        Negative indices count back from the end, as they do everywhere else in
        Python. An index outside the sequence is reported as a failure naming the
        length that was actually there, never raised as an ``IndexError`` -- an
        assertion answers, it does not blow up.

        ``found is value or found == value`` is Python's membership rule, applied
        here for the reason it is applied everywhere else in the module: the item
        the caller handed over is the item at that index even when it declines to
        equal itself.

        The continuation carries the item that was *stored*, so anything asserted
        through ``.which`` runs against the sequence's own object rather than the
        one passed in.
        """
        subject = self._subject
        count = len(subject)
        if -count <= index < count:
            found = subject[index]
            if found is value or found == value:
                return Found(self, found)
            return cast(
                "Found[Self, E]",
                self._fail_narrowing(
                    f"to have {format_value(value)} at index {index},"
                    f" but had {format_value(found)}: {render_items(subject)}",
                    because,
                ),
            )
        return cast(
            "Found[Self, E]",
            self._fail_narrowing(
                f"to have an item at index {index}, but only had {count}: {render_items(subject)}",
                because,
            ),
        )
