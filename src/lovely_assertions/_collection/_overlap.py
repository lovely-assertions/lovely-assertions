"""Intersection, and the two that say exactly what may be there.

``contains_only`` is the strictest claim in this file and the one worth being
careful with: it fails for an item nobody expected *and* for one nobody supplied,
and a message that did not say which is which would be no use at all.
"""

from typing import TYPE_CHECKING, Any, Self

from lovely_assertions._collection._base import CollectionBase
from lovely_assertions._collection._clauses import NEEDS_VALUES, items_inside, items_outside
from lovely_assertions._collection._comparison import any_inside, none_outside
from lovely_assertions._collection._render import render_items
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Collection

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class OverlapAssertions[E, C: Collection[Any] = Collection[E]](CollectionBase[E, C]):
    """What two collections share, and the exact-contents pair."""

    __slots__ = ()

    def intersects(self, other: "Collection[E]", /, *, because: str = "") -> Self:
        """Assert the collection shares at least one item with ``other``."""
        subject = self._subject
        if any_inside(subject, other):
            return self
        return self._fail(
            f"to intersect {render_items(other)}, but shared nothing with {render_items(subject)}",
            because,
        )

    def does_not_intersect(self, other: "Collection[E]", /, *, because: str = "") -> Self:
        """Assert the collection shares no item with ``other``."""
        subject = self._subject
        if not any_inside(subject, other):
            return self
        return self._fail(
            f"not to intersect {render_items(other)},"
            f" but shared {render_items(items_inside(subject, other))}",
            because,
        )

    def is_disjoint_from(self, other: "Collection[E]", /, *, because: str = "") -> Self:
        """Assert the collection shares no item with ``other`` -- the set-theory spelling.

        An alias of :meth:`does_not_intersect`, and deliberately not a second
        implementation: two assertions that ask the same question must not be able
        to answer it differently. It reports through the canonical message, the
        way :meth:`contains_no_duplicates` reports through
        :meth:`has_unique_items`.
        """
        return self.does_not_intersect(other, because=because)

    def contains_only(self, *items: E, because: str = "") -> Self:
        """Assert the collection holds exactly ``items`` -- order and repeats ignored.

        Both directions are checked: nothing outside ``items`` may be present, and
        nothing in ``items`` may be missing. That is what "only" means in
        AssertJ's ``containsOnly`` and in this library's own
        :meth:`~lovely_assertions._mapping.MappingExpect.contains_only_keys`, and
        an assertion whose name matches one of those while its behaviour matches
        the other would be a trap.

        The subset-only reading is still available, spelled as what it is::

            expect(statuses).is_subset_of({"ok", "pending"})

        A call with no items asserts the collection is *empty*, which is a real
        assertion rather than a vacuous one -- so, unlike the other variadics
        here, it is allowed (the same exception ``contains_only_keys`` gets).
        """
        subject = self._subject
        if none_outside(subject, items) and none_outside(items, subject):
            return self
        missing = items_outside(items, subject)
        surplus = items_outside(subject, items)
        if not missing:
            return self._fail(
                f"to contain only {render_items(items)}, but also had {render_items(surplus)}",
                because,
            )
        if not surplus:
            return self._fail(
                f"to contain only {render_items(items)}, but was missing {render_items(missing)}",
                because,
            )
        return self._fail(
            f"to contain only {render_items(items)}, but was missing {render_items(missing)}"
            f" and also had {render_items(surplus)}",
            because,
        )

    def contains_none_of(self, *items: E, because: str = "") -> Self:
        """Assert not one of ``items`` appears in the collection.

        This is the "none of these" half of the multi-item family; there is no
        ``does_not_contain_any``, because it would be this assertion under a
        second name. :meth:`~lovely_assertions._string.StringExpect.does_not_contain_any`
        exists on the string subject, which has no ``contains_none_of``.
        """
        if not items:
            raise ValueError(NEEDS_VALUES)
        subject = self._subject
        if not any_inside(items, subject):
            return self
        return self._fail(
            f"not to contain any of {render_items(items)},"
            f" but had {render_items(items_inside(items, subject))}",
            because,
        )
