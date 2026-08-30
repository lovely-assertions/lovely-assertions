"""The override that re-earns the ordered catalogue.

The inherited declaration hands back an order-free subject, because the order of
a list extracted from a ``set`` is the set's iteration order and nothing worth
asserting about. Here the source *is* ordered and extraction preserves that, so
``is_sorted`` on the result is the question it appears to be.

The import that rebuilds the subject is deferred, for the reason it is on the
collection seam of the same name: what a projection re-enters is decided by the
value, not by the module graph.
"""

from typing import TYPE_CHECKING, override

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._sequence._base import SequenceBase

if TYPE_CHECKING:
    from collections.abc import Callable

    from lovely_assertions._sequence import SequenceExpect

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class ProjectionAssertions[E](SequenceBase[E]):
    """Deriving an ordered subject from an ordered one."""

    __slots__ = ()

    @override
    def extracting[R](self, selector: "Callable[[E], R]", /) -> "SequenceExpect[R]":
        """Assert about one field of every item, keeping the order they were in.

        ::

            expect(orders).extracting(lambda order: order.total).is_sorted()

        The override that re-earns the ordered catalogue. The base declaration on
        :class:`~lovely_assertions._collection.CollectionExpect` hands back an
        order-free subject, because the order of a list extracted from a ``set``
        is the set's iteration order and nothing worth asserting about. Here the
        source *is* ordered, extraction preserves that order item for item, so
        ``is_sorted`` on the result is the question it appears to be.

        Everything the base says still holds: the callable form only -- the string
        form assertpy is known for is untypeable -- no ``because``, because this
        makes no claim and cannot fail, and an explicit subject name carries over.
        """
        # Deferred: this file is a seam of the very class it builds, so naming
        # it at module level is a cycle through the package's front door.
        from lovely_assertions._sequence import SequenceExpect  # noqa: PLC0415

        return self._carrying_name(SequenceExpect([selector(item) for item in self._subject]))
