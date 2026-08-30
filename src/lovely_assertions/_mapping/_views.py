"""Handing the keys or the values to the collection subject.

Which is what makes the whole unordered catalogue available without this file
declaring any of it. The views are what Python already gives; what is added is
that they arrive as a subject rather than as a bare view.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING

from lovely_assertions._collection import CollectionExpect
from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Collection

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class ViewAssertions[K, V](Expect[Mapping[K, V]]):
    """The keys and the values as collections of their own."""

    __slots__ = ()

    #
    # A mapping is a collection of its keys and a collection of its values, and
    # both of those already have a full catalogue one module over: uniqueness,
    # subset and superset, element types, wildcard matching, nested inspection.
    # Re-declaring any of it here would be a second implementation of an already
    # answered question, which is how one question comes to have two answers, so
    # the views hand back the collection subject instead. `expect()` dispatches
    # `dict.keys()` there already, which is what makes this a continuation
    # rather than new machinery.
    #
    # Properties, not methods, to match `.and_`, `.which` and `.whose_value`.
    # A continuation is a step sideways in the sentence, and
    # `expect(rows).keys()` would read as a call *on the mapping*.
    #
    # There is deliberately no `items` view. Every question the collection
    # catalogue could put to `(key, value)` pairs is either answered better here
    # -- `contains_entry` says *"but that key held 'ada'"* where
    # `items.contains(("name", "bob"))` could only reprint the pairs -- or
    # vacuous, since keys are unique and therefore so are pairs, which makes
    # `has_unique_items` on them a test that cannot fail. The one genuine use
    # left, comparing entries against another mapping's, is still one
    # `expect(rows.items())` away, and that already lands on `CollectionExpect`.
    def _view[E](self, items: "Collection[E]", /) -> "CollectionExpect[E]":
        """Wrap one of the mapping's views, carrying an explicit name across.

        Not the failure path -- this runs whenever a view is taken -- so it stays
        to the one allocation the wrapper itself is, plus one attribute read.
        ``_name`` is unset unless the caller named the subject, hence the
        default. A view that dropped the name would silently fall back to
        recovering one from the source, which is the answer ``described_as``
        was called to override in the first place.
        """
        view: CollectionExpect[E] = CollectionExpect(items)
        name = getattr(self, "_name", None)
        if isinstance(name, str):
            view.described_as(name)
        return view

    @property
    def keys(self) -> "CollectionExpect[K]":
        """Continue on the keys, as a collection.

            expect(rows).keys.is_subset_of(ALLOWED_FIELDS)

        Deliberately not ``has_unique_items``: keys cannot repeat, so that one
        is a test that cannot fail -- the very reason the block above gives for
        there being no ``items`` view. What the keys view is *for* is the
        questions the mapping catalogue does not answer at all: subset and
        superset, element types, wildcard matching, nested inspection.

        The wrapper holds the live view, so this copies nothing. Note that
        ``.and_`` on the result re-chains on the *keys*: the view is a subject in
        its own right, not a continuation that remembers the mapping.
        """
        return self._view(self._subject.keys())

    @property
    def values(self) -> "CollectionExpect[V]":
        """Continue on the values, as a collection.

            expect(rows).values.all_are_instance_of(int)

        Unlike the keys, values may repeat -- ``has_unique_items`` is a real
        question here, and the usual reason to reach for this view.
        """
        return self._view(self._subject.values())
