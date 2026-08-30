"""Comparing what two graphs are made of, rather than asking their types.

``==`` is the object's own opinion, and a class that never defined one says two
instances with identical fields are different. This is the other question: are
these built out of the same things? Two objects of unrelated types can be
equivalent; two of the same type can differ in a field neither ``__eq__`` reads.
"""

from typing import TYPE_CHECKING, Self

from lovely_assertions._diff import render_operand
from lovely_assertions._equivalence import compare, differs, equivalency
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from lovely_assertions._equivalence import Equivalency
from lovely_assertions._core._base import ExpectBase

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

#: The default equivalence configuration, built once. It is immutable, so a
#: shared instance is safe, and building one per call would be an allocation
#: on the path of an assertion that is about to walk two graphs anyway.
_ANY_SHAPE = equivalency()


class EquivalenceAssertions[T](ExpectBase[T]):
    """The assertions of the ``structural equivalence`` seam."""

    __slots__ = ()

    def is_equivalent_to(
        self,
        expected: object,
        /,
        *,
        options: "Equivalency | None" = None,
        because: str = "",
    ) -> Self:
        """Assert the subject matches ``expected`` member by member, recursively.

        Where :meth:`is_equal_to` asks the subject's ``__eq__``, this walks both
        graphs and compares what they are made of -- dataclasses, NamedTuples,
        attrs and pydantic models, mappings, collections, and anything with
        ``__slots__`` or a ``__dict__``. So two objects of unrelated types that
        carry the same values are equivalent, and a type that never defined
        ``__eq__`` can be compared at all::

            expect(response).is_equivalent_to(
                expected, options=equivalency().excluding("id", "created_at")
            )

        ``options`` is an immutable builder, so one configuration can be named at
        module scope and reused across a suite. Every difference is reported at
        once, each with the path that locates it -- ``address.city``,
        ``items[3]`` -- and those paths are exactly what
        :meth:`~lovely_assertions.Equivalency.excluding_path` accepts.

        **Ordering is strict by default**, which is the opposite of
        FluentAssertions and deliberate: in Python a ``list`` is ordered by
        definition and ``set`` exists for the other case, so a default that let
        ``[1, 2]`` match ``[2, 1]`` would pass tests that ought to fail. Say
        ``ignoring_order()`` when you mean it.
        """
        report = compare(self._subject, expected, options if options is not None else _ANY_SHAPE)
        if not report:
            return self
        return self._fail(f"to be equivalent to {render_operand(expected)}{report}", because)

    def is_not_equivalent_to(
        self,
        expected: object,
        /,
        *,
        options: "Equivalency | None" = None,
        because: str = "",
    ) -> Self:
        """Assert the subject differs from ``expected`` somewhere.

        The complement of :meth:`is_equivalent_to`, and it takes the same options
        -- asserting that two payloads differ *once the volatile fields are
        excluded* is the useful form, and it needs the same exclusions.

        Asked through :func:`~lovely_assertions._equivalence.differs` rather than
        :func:`~lovely_assertions._equivalence.compare`, because this is the one
        assertion whose **passing** branch is the expensive one: a report of every
        difference, built and then dropped unread. ``differs`` is the same walk
        stopped at the first disagreement.
        """
        if differs(self._subject, expected, options if options is not None else _ANY_SHAPE):
            return self
        return self._fail(f"not to be equivalent to {render_operand(expected)}", because)
