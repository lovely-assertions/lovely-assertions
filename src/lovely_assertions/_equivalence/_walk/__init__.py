"""The traversal: one pair of values at a time, one link of a chain per kind.

A comparison threads five things through every level -- the options, the memo, the
findings, the budget, and whether this walk is deciding a pairing or describing a
graph -- so the recursion is written as a class whose methods call one another
rather than as functions carrying that plumbing alongside the two arguments of
subject. This package is that class, cut into one module per kind of value it has
to take apart.

The links form a single chain, each a subclass of the one before it and none of
them adding state -- every link above the root declares empty ``__slots__`` -- so
a walk stays one small object however many links it is assembled from.
:class:`WalkState` holds the fields; then selection, records, mappings,
order-insensitive pairing, sequences, and the router that hands a composite pair
to whichever of those its kind calls for. The order is what each
link needs from its ancestors. The two calls that point the other way -- back into
a whole comparison, and out to the router -- are declared on :class:`WalkState` and
implemented at the far end, which is what lets a recursion between the links be
written as a chain at all.

:class:`Walk` closes it here, in the package's own module, because it is the one
name none of the links may mention: the pairing link builds a second walk through
``type(self)`` for exactly that reason. What this module owns besides is the order
of the questions a pair is settled by before it is ever handed to the router --
identity, a registered comparator, then enum names -- and the guard around the
comparator, which is a caller's code and is allowed to raise.
"""

from typing import TYPE_CHECKING, Any, override

from lovely_assertions._equivalence._findings import note_difference, pair_difference
from lovely_assertions._equivalence._reading import comparator_for, enum_names
from lovely_assertions._equivalence._walk._structure import StructureWalk
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Callable

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class Walk(StructureWalk):
    """One traversal of the two graphs: the options, the memo, the findings.

    Written as methods rather than free functions for a plain reason: the recursion
    threads five things through every level, and a free function taking those
    alongside the path and the depth is seven arguments of plumbing around two of
    subject.

    The memo -- see :class:`Memo` -- holds ``(id(actual), id(expected))`` for
    every pair currently being compared, which is ``_formatters._RENDERING``'s
    trick with a different carrier. That one has to be a ``ContextVar`` because it
    is re-entered through user code it did not call; this recursion is entirely
    its own, so the memo travels with it -- and a custom comparator that calls
    back into ``is_equivalent_to`` gets a fresh memo, which is the correct answer
    rather than a shared one.
    """

    __slots__ = ()

    @override
    def compare(self, actual: object, expected: object, path: str, depth: int, /) -> None:
        """Compare one pair, recording whatever it finds.

        The order of the four settling questions is the whole design. Identity
        first, because an object is equivalent to itself under any configuration
        and the check is free. Then a custom comparator, because a caller who
        registered one for this type said that its members are not what they want
        compared. Then enum names, for the same reason. The fourth is the router's
        own first move, ``==`` -- **equality settles equivalence**: two values that
        are equal hold the same information, and taking a graph apart to rediscover
        that would be work spent to reach the answer already in hand.
        """
        if actual is expected or self.findings.full:
            return
        if self.matching:
            self.budget.spend_comparison()
        options = self.options
        if options.comparators:
            comparator = comparator_for(actual, expected, options.comparators)
            if comparator is not None:
                self._by_comparator(comparator, actual, expected, path)
                return
        if options.enums_by_name:
            names = enum_names(actual, expected)
            if names is not None:
                if names[0] != names[1]:
                    self.findings.add(pair_difference(path, actual, expected))
                return
        self._by_structure(actual, expected, path, depth)

    def _by_comparator(
        self,
        comparator: "Callable[[Any, Any], bool]",
        actual: object,
        expected: object,
        path: str,
        /,
    ) -> None:
        """Let a registered comparator settle one pair, and survive one that will not."""
        try:
            agreed = bool(comparator(actual, expected))
        # a comparator is user code; its failure is a finding, not a crash
        except Exception as error:
            self.findings.add(
                note_difference(
                    path,
                    "the comparator for "
                    + type(actual).__name__
                    + " raised "
                    + type(error).__name__,
                )
            )
            return
        if not agreed:
            self.findings.add(pair_difference(path, actual, expected))
