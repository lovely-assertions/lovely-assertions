"""The six subset and superset forms.

Set relations without requiring a ``set``: the subject may be a list, and the
comparison decides per call whether a hash table would answer sooner. The failure
names the items that put the relation out, not the whole of either side.
"""

from typing import TYPE_CHECKING, Any, Self

from lovely_assertions._collection._base import CollectionBase
from lovely_assertions._collection._clauses import items_outside
from lovely_assertions._collection._comparison import none_outside
from lovely_assertions._collection._render import render_items
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Collection

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class RelationAssertions[E, C: Collection[Any] = Collection[E]](CollectionBase[E, C]):
    """Subset and superset, proper and not."""

    __slots__ = ()

    def is_subset_of(self, other: "Collection[E]", /, *, because: str = "") -> Self:
        """Assert every item also appears in ``other``.

        The failure lists the items that were *not* in ``other`` -- the part of
        the subject that made it fail -- rather than printing both collections
        and leaving the difference to the reader.
        """
        subject = self._subject
        if none_outside(subject, other):
            return self
        return self._fail(
            f"to be a subset of {render_items(other)},"
            f" but also had {render_items(items_outside(subject, other))}",
            because,
        )

    def is_not_subset_of(self, other: "Collection[E]", /, *, because: str = "") -> Self:
        """Assert at least one item is missing from ``other``.

        An empty collection is a subset of everything, so this fails on one -- and
        says which of the two reasons it was, because "every item was in it" in
        front of an empty collection reads like a bug in the library.
        """
        subject = self._subject
        if not none_outside(subject, other):
            return self
        if len(subject) == 0:
            return self._fail(
                f"not to be a subset of {render_items(other)}, but it had no items"
                f" -- an empty collection is a subset of anything",
                because,
            )
        return self._fail(
            f"not to be a subset of {render_items(other)}, but every item was in it", because
        )

    def is_superset_of(self, other: "Collection[E]", /, *, because: str = "") -> Self:
        """Assert every item of ``other`` also appears here.

        The mirror of :meth:`is_subset_of`, and read the same way: membership,
        with repeats ignored. A collection is a superset of ``other`` when nothing
        in ``other`` is missing, however many times either side holds it.
        """
        subject = self._subject
        if none_outside(other, subject):
            return self
        return self._fail(
            f"to be a superset of {render_items(other)},"
            f" but was missing {render_items(items_outside(other, subject))}",
            because,
        )

    def is_not_superset_of(self, other: "Collection[E]", /, *, because: str = "") -> Self:
        """Assert at least one item of ``other`` is missing here.

        Everything is a superset of an empty collection, so this fails on one --
        and says so, for the reason :meth:`is_not_subset_of` does.
        """
        subject = self._subject
        if not none_outside(other, subject):
            return self
        if len(other) == 0:
            return self._fail(
                f"not to be a superset of {render_items(other)}, but there was nothing"
                f" it could be missing -- everything is a superset of an empty collection",
                because,
            )
        return self._fail(
            f"not to be a superset of {render_items(other)},"
            f" but it held every item: {render_items(subject)}",
            because,
        )

    def is_proper_subset_of(self, other: "Collection[E]", /, *, because: str = "") -> Self:
        """Assert every item is in ``other``, and ``other`` holds something more.

        "Proper" is the difference between ``<=`` and ``<``: two collections
        holding the same items are subsets of each other and proper subsets of
        neither. The failure says which of the two halves gave way.
        """
        subject = self._subject
        if not none_outside(subject, other):
            return self._fail(
                f"to be a proper subset of {render_items(other)},"
                f" but also had {render_items(items_outside(subject, other))}",
                because,
            )
        if none_outside(other, subject):
            return self._fail(
                f"to be a proper subset of {render_items(other)}, but they held the same items",
                because,
            )
        return self

    def is_proper_superset_of(self, other: "Collection[E]", /, *, because: str = "") -> Self:
        """Assert every item of ``other`` is here, and something else besides."""
        subject = self._subject
        if not none_outside(other, subject):
            return self._fail(
                f"to be a proper superset of {render_items(other)},"
                f" but was missing {render_items(items_outside(other, subject))}",
                because,
            )
        if none_outside(subject, other):
            return self._fail(
                f"to be a proper superset of {render_items(other)}, but they held the same items",
                because,
            )
        return self
