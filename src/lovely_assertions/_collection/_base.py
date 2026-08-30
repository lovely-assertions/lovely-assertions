"""The shared root of every seam, and the four hooks they all call.

A collection message says *where* something was found, and the answer differs by
subject: a sequence has indices, a mapping has keys, a set has neither. The four
hooks here are what a seam asks instead of deciding for itself, so one override
in a subclass re-words every assertion it inherits at once.
"""

from collections.abc import Collection
from typing import TYPE_CHECKING, Any

from lovely_assertions._collection._clauses import offender
from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._formatting import current_formatting

if TYPE_CHECKING:
    from collections.abc import Callable

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class CollectionBase[E, C: Collection[Any] = Collection[E]](Expect[C]):
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
        index, item = offender(self._subject, offends, found)
        return format_value(item) + self._position(index)

    def _names_type(self, offends: "Callable[[E], bool]", found: "tuple[int, E]", /) -> str:
        """The same clause, plus the type that made the item an offence. Failure path only."""
        index, item = offender(self._subject, offends, found)
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
