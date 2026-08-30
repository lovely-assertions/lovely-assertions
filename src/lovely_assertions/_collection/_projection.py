"""Deriving one collection from another, and carrying the name across.

``extracting`` re-enters the subject constructor, which is a property of the
value being projected rather than of the module graph -- so the import that does
it is paid at the call, not at import time, and this file stays a leaf of the
package rather than a cycle through its front door.
"""

from typing import TYPE_CHECKING, Any

from lovely_assertions._collection._base import CollectionBase
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Callable, Collection

    from lovely_assertions._collection import CollectionExpect
    from lovely_assertions._core import Expect

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class ProjectionAssertions[E, C: Collection[Any] = Collection[E]](CollectionBase[E, C]):
    """Continue on something derived from each item."""

    __slots__ = ()

    def _carrying_name[D: "Expect[Any]"](self, derived: D, /) -> D:
        """Hand an explicit subject name on to a subject derived from this one.

        A derived wrapper is a new object and has no name, so a failure reported
        against it falls back to reading the source line -- which finds
        ``expect(rows)`` and is right often enough. It is wrong in exactly the two
        places :meth:`~lovely_assertions._core.Expect.described_as` exists to fix:
        a loop, where every iteration names the same variable, and a helper, where
        the line names the parameter rather than the caller's value. An explicit
        name has to survive at least as well as a recovered one, or naming the
        subject stops being worth doing.

        Not the failure path -- but not an assertion's happy path either: nothing
        calls this except a transformation that is already materialising a list.
        """
        name = getattr(self, "_name", None)
        return derived if name is None else derived.described_as(name)

    def extracting[R](self, selector: "Callable[[E], R]", /) -> "CollectionExpect[R]":
        """Assert about one field of every item instead of about the items.

        assertpy's most-loved feature, typed::

            expect(orders).extracting(lambda order: order.customer).contains_only("ana")

        **The callable form only.** ``extracting("customer")`` is the spelling
        assertpy is known for and it cannot be typed: a checker cannot know that
        the attribute exists, and it certainly cannot know what type it has, so
        every assertion downstream of the string form would be checked against
        ``Any`` -- an autocomplete list that is empty and a type error that never
        fires. The callable survives a rename, and ``R`` is inferred from it, so
        the returned subject carries a real element type.

        This is a transformation, not an assertion: it makes no claim, so it
        cannot fail and takes no ``because``. A selector that raises propagates,
        the way a broken inspector does -- that is a bug in the test rather than a
        finding about the subject.

        **The result is a collection, not a sequence**, and that is the whole
        design. Extraction materialises a list, so returning a
        ``SequenceExpect`` would type-check and would be a trap: the order of that
        list is the *source's* iteration order, and a ``set`` has none worth
        asserting about. ``expect(tags).extracting(len).is_sorted()`` would then
        compile and pass or fail on hash order.
        :class:`~lovely_assertions._sequence.SequenceExpect` overrides this to
        return a sequence subject, which is where the ordered catalogue is
        honestly available -- the same split, one level down.

        A name given with ``described_as`` or ``expect(..., name=...)`` carries
        over; see :meth:`_carrying_name`.
        """
        # Deferred: this file is a seam of the very class it builds, so naming
        # it at module level is a cycle through the package's front door. What
        # a projection re-enters is decided by the value, not by the graph.
        from lovely_assertions._collection import CollectionExpect  # noqa: PLC0415

        extracted: CollectionExpect[R] = CollectionExpect(
            [selector(item) for item in self._subject]
        )
        return self._carrying_name(extracted)
