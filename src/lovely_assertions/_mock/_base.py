"""The shared root of every mock seam, and the one clause they all use.

Three of the four seams fail into the same sentence -- what the mock was actually
called with, or that it was not called at all -- and a message that said only
"not called with those arguments" would leave the reader to go and print the mock
themselves. One method here re-words every assertion that inherits it.
"""

from typing import TYPE_CHECKING, Any

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._mock._rendering import render_calls, render_options
from lovely_assertions._text import count_of

if TYPE_CHECKING:
    from collections.abc import Sequence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class MockBase(Expect[Any]):
    """What every seam of the mock subject can say about the calls it saw."""

    __slots__ = ()

    def _how_it_was_called(self) -> str:
        """The ``but ...`` half of a message about the call count. Failure path only.

        One helper for every count-shaped failure, so ``was_not_called``,
        ``was_called_once`` and ``has_call_count`` cannot drift into three
        different accounts of the same fact. No f-string: the message is built
        inside the ``_fail`` call, so a passing assertion formats nothing.
        """
        recorded: Sequence[Any] = self._subject.call_args_list
        if not recorded:
            return "it was never called"
        options = render_options()
        return (
            "it was called "
            + count_of(len(recorded), "time")
            + ": "
            + render_calls(recorded, options)
        )

    def _carrying_name[D: "Expect[Any]"](self, derived: D, /) -> D:
        """Hand an explicit subject name on to a subject derived from this one.

        The same five lines as
        :meth:`~lovely_assertions._collection.CollectionExpect._carrying_name`
        and for the same reason: a derived wrapper is a new object with no name,
        and an explicit name has to survive at least as well as a recovered one
        or naming the subject stops being worth doing. It is duplicated rather
        than shared because the shared home would be ``Expect`` itself, and that
        is a change to a module this one does not own.
        """
        name = getattr(self, "_name", None)
        return derived if name is None else derived.described_as(name)
