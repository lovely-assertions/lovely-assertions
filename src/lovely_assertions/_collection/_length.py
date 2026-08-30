"""How many items, compared nine ways.

The comparisons are spelled out rather than folded into one method taking an
operator, because the assertion a reader writes is the sentence they mean and a
failure that says "length is not greater than 3" reads better than one that says
a comparison failed.
"""

from typing import TYPE_CHECKING, Any, Self

from lovely_assertions._collection._base import CollectionBase
from lovely_assertions._collection._render import render_items
from lovely_assertions._core import describe_predicate
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._text import count_of

if TYPE_CHECKING:
    from collections.abc import Callable, Collection

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class LengthAssertions[E, C: Collection[Any] = Collection[E]](CollectionBase[E, C]):
    """How many, in every form the question is asked."""

    __slots__ = ()

    def has_length(self, expected: int, /, *, because: str = "") -> Self:
        """Assert the collection has exactly ``expected`` items."""
        subject = self._subject
        if len(subject) == expected:
            return self
        return self._fail(
            f"to have length {expected}, but had {len(subject)}: {render_items(subject)}", because
        )

    def does_not_have_length(self, unexpected: int, /, *, because: str = "") -> Self:
        """Assert the collection has any length but ``unexpected``."""
        subject = self._subject
        if len(subject) != unexpected:
            return self
        return self._fail(
            f"not to have length {unexpected}, but was {render_items(subject)}", because
        )

    def has_length_matching(
        self, predicate: "Callable[[int], bool]", /, *, because: str = ""
    ) -> Self:
        """Assert the collection's length satisfies ``predicate``."""
        subject = self._subject
        if predicate(len(subject)):
            return self
        return self._fail(
            f"to have a length matching {describe_predicate(predicate)},"
            f" but had {len(subject)}: {render_items(subject)}",
            because,
        )

    def has_length_greater_than(self, other: int, /, *, because: str = "") -> Self:
        """Assert the collection has more than ``other`` items."""
        subject = self._subject
        if len(subject) > other:
            return self
        return self._fail(
            f"to have more than {count_of(other, 'item')},"
            f" but had {len(subject)}: {render_items(subject)}",
            because,
        )

    def has_length_greater_than_or_equal_to(self, other: int, /, *, because: str = "") -> Self:
        """Assert the collection has at least ``other`` items."""
        subject = self._subject
        if len(subject) >= other:
            return self
        return self._fail(
            f"to have at least {count_of(other, 'item')},"
            f" but had {len(subject)}: {render_items(subject)}",
            because,
        )

    def has_length_less_than(self, other: int, /, *, because: str = "") -> Self:
        """Assert the collection has fewer than ``other`` items."""
        subject = self._subject
        if len(subject) < other:
            return self
        return self._fail(
            f"to have fewer than {count_of(other, 'item')},"
            f" but had {len(subject)}: {render_items(subject)}",
            because,
        )

    def has_length_less_than_or_equal_to(self, other: int, /, *, because: str = "") -> Self:
        """Assert the collection has at most ``other`` items."""
        subject = self._subject
        if len(subject) <= other:
            return self
        return self._fail(
            f"to have at most {count_of(other, 'item')},"
            f" but had {len(subject)}: {render_items(subject)}",
            because,
        )

    def has_same_length_as(self, other: "Collection[object]", /, *, because: str = "") -> Self:
        """Assert the collection is as long as ``other``.

        ``other`` is any collection: comparing a set against a list or against a
        mapping's keys is a fair question, and the element types are nobody's
        business here.
        """
        subject = self._subject
        if len(subject) == len(other):
            return self
        return self._fail(
            f"to have the same length as {render_items(other)},"
            f" but had {count_of(len(subject), 'item')} against {len(other)}",
            because,
        )

    def does_not_have_same_length_as(
        self, other: "Collection[object]", /, *, because: str = ""
    ) -> Self:
        """Assert the collection is not as long as ``other``."""
        subject = self._subject
        if len(subject) != len(other):
            return self
        return self._fail(
            f"not to have the same length as {render_items(other)},"
            f" but both had {count_of(len(subject), 'item')}",
            because,
        )
