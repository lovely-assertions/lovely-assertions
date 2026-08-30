"""The shared root, and the two hooks that say where something was found.

A sequence has indices, so the inherited collection catalogue reports positions
through these two rather than deciding for itself. One override here re-words
every assertion the subject inherits.
"""

from collections.abc import Sequence
from typing import override

from lovely_assertions._collection import CollectionExpect
from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class SequenceBase[E](CollectionExpect[E, Sequence[E]]):
    """Assertions for sequences, parameterised by element type.

    The subject is a ``Sequence``, not a ``list``: indexing, ``len`` and repeated
    iteration are fair game, mutation is not, and one subject class covers lists,
    tuples and anything else that behaves like a sequence.

    Everything an unordered collection can also answer is inherited from
    :class:`~lovely_assertions._collection.CollectionExpect`; what is declared
    here is what an order makes meaningful.
    """

    __slots__ = ()

    #
    # The two hooks the inherited catalogue reports positions through. Failure
    # path only, and no f-strings: a failure message is assembled in exactly one
    # place, inside `_fail`, and these only hand it a fragment.
    @override
    def _position(self, index: int, /) -> str:
        """The `` at index N`` clause that follows a rendered item."""
        return " at index " + str(index)

    @override
    def _finding_tag(self, index: int, /) -> str:
        """The ``at index N: `` tag in front of one nested finding."""
        return "at index " + str(index) + ": "
