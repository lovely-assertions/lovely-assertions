"""Emptiness, and the two that treat ``None`` as a kind of empty.

``is_none_or_empty`` exists because the two are the same bug in most tests --
a value that was never populated -- and asking twice is a line of noise.
"""

from typing import TYPE_CHECKING, Any, Self

from lovely_assertions._collection._base import CollectionBase
from lovely_assertions._collection._comparison import is_none_or_empty
from lovely_assertions._collection._render import render_items, render_or_none
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Collection

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class EmptinessAssertions[E, C: Collection[Any] = Collection[E]](CollectionBase[E, C]):
    """Nothing in it, something in it, and the None-absorbing pair."""

    __slots__ = ()

    def is_empty(self, *, because: str = "") -> Self:
        """Assert the collection has no items."""
        subject = self._subject
        if len(subject) == 0:
            return self
        return self._fail(f"to be empty, but was {render_items(subject)}", because)

    def is_not_empty(self, *, because: str = "") -> Self:
        """Assert the collection has at least one item."""
        if len(self._subject) > 0:
            return self
        return self._fail("not to be empty, but it was", because)

    def is_none_or_empty(self, *, because: str = "") -> Self:
        """Assert the collection is ``None`` or has no items.

        The subject type excludes ``None``, so a checker will say this can only
        ever be the empty case. The runtime check is real all the same: ``None``
        arrives here through a cast, from untyped code, or from a fixture that
        returned nothing, and absorbing exactly that is what the assertion is for.
        """
        if is_none_or_empty(self._subject):
            return self
        return self._fail(f"to be None or empty, but was {render_items(self._subject)}", because)

    def is_not_none_or_empty(self, *, because: str = "") -> Self:
        """Assert the collection is neither ``None`` nor empty."""
        if not is_none_or_empty(self._subject):
            return self
        return self._fail(
            f"not to be None or empty, but was {render_or_none(self._subject)}", because
        )
