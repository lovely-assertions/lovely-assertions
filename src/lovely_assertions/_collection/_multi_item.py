"""The same relations, written the way a test usually wants them.

``contains_all("a", "b")`` rather than ``is_superset_of({"a", "b"})``. The same
answer, and the refusal of a call with no arguments -- an assertion that cannot
fail is the one kind of test worse than a wrong one.
"""

from typing import TYPE_CHECKING, Any, Self

from lovely_assertions._collection._base import CollectionBase
from lovely_assertions._collection._clauses import NEEDS_VALUES, items_outside
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


class MultiItemAssertions[E, C: Collection[Any] = Collection[E]](CollectionBase[E, C]):
    """The variadic spellings of the relations above."""

    __slots__ = ()

    #
    # The variadic spellings of the set relations just above: `contains_all` asks
    # what `is_superset_of` asks, `contains_any` what `intersects` asks. They ship
    # because the call shape is the difference that matters at a call site --
    # `contains_all("a", "b")` against `is_superset_of({"a", "b"})` -- and because
    # the string subject offers the same names, so a reader who found them there
    # has every reason to expect them here.
    #
    # They are not second implementations. Each one asks its question through the
    # same helper as the relation it mirrors, so the two can differ in wording and
    # cannot differ in the answer.
    def contains_all(self, *items: E, because: str = "") -> Self:
        """Assert every one of ``items`` appears in the collection.

        Extras are allowed: this is containment, not equality. :meth:`contains_only`
        is the assertion that closes the other direction, and
        :meth:`is_superset_of` the one that takes a collection rather than a list
        of arguments.
        """
        if not items:
            raise ValueError(NEEDS_VALUES)
        subject = self._subject
        if none_outside(items, subject):
            return self
        return self._fail(
            f"to contain all of {render_items(items)},"
            f" but was missing {render_items(items_outside(items, subject))}",
            because,
        )

    def does_not_contain_all(self, *items: E, because: str = "") -> Self:
        """Assert at least one of ``items`` is absent.

        The negation of :meth:`contains_all`, so one absence satisfies it.
        :meth:`contains_none_of` is the stricter one, which demands every one of
        them be absent -- the pairing
        :meth:`~lovely_assertions._string.StringExpect.does_not_contain_all` and
        ``does_not_contain_any`` have on the string subject.
        """
        if not items:
            raise ValueError(NEEDS_VALUES)
        subject = self._subject
        if not none_outside(items, subject):
            return self
        return self._fail(
            f"not to contain all of {render_items(items)},"
            f" but it held every one of them: {render_items(subject)}",
            because,
        )

    def contains_any(self, *items: E, because: str = "") -> Self:
        """Assert at least one of ``items`` appears in the collection."""
        if not items:
            raise ValueError(NEEDS_VALUES)
        subject = self._subject
        if any_inside(items, subject):
            return self
        return self._fail(
            f"to contain at least one of {render_items(items)}, but was {render_items(subject)}",
            because,
        )
