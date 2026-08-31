"""The router, and the bookkeeping that decides what a finished pair is remembered for.

Two things live here, and they are really one. Sending a composite pair to the
branch for its kind is a short list of comparisons; wrapped around it is
everything that makes the walk cost nodes rather than paths -- the check that this
pair at this depth has already been shown equivalent, the marker that lets a graph
containing itself terminate instead of recursing until the stack runs out, and the
question asked on the way back out about whether the verdict just reached is a
fact about the pair or only about the pair *here*.

That last question is the reason for the file. Its answer has to hold for a value
that cycles, for a value the caller excluded a branch of, for the two at once, and
for an ``id`` the interpreter has handed out twice; alongside a list of kinds each
of those would read as a special case, when together they are one argument. The
other side of the same protocol -- what a marker means, and the hazards it has to
survive -- is on :class:`Memo`.
"""

from typing import override

from lovely_assertions._equivalence._classification import KIND_MAPPING, KIND_SEQUENCE, KIND_SET
from lovely_assertions._equivalence._memo import NOTHING_OPEN
from lovely_assertions._equivalence._reading import equal_or_unknown
from lovely_assertions._equivalence._walk._sequence import SequenceWalk
from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class StructureWalk(SequenceWalk):
    """The link that routes a composite pair by kind, and decides what its verdict outlives.

    The last link before the concrete walk, and necessarily the last:
    :meth:`_members` reaches into every branch its ancestors define -- mappings,
    sets, sequences, records -- and every one of those reaches back here through
    :meth:`compare`. That :meth:`_by_structure` is *declared* on
    :class:`WalkState` and only implemented here is what keeps a reach in both
    directions from asking a link to name one of its own subclasses.
    """

    __slots__ = ()

    def _members(
        self,
        actual: object,
        expected: object,
        resolved: tuple[str, tuple[str, ...], tuple[str, ...]],
        path: str,
        depth: int,
        /,
    ) -> None:
        """Route a composite pair of one kind to the branch that walks it.

        The kind and the field names are carried in rather than recovered:
        resolving a record's fields runs ``dataclasses.fields`` or walks an MRO,
        and doing it twice per node is work the caller has already done.
        """
        kind, actual_names, expected_names = resolved
        if kind == KIND_MAPPING:
            self._mapping(actual, expected, path, depth)
        elif kind == KIND_SET:
            self._set(actual, expected, path, depth)
        elif kind == KIND_SEQUENCE:
            self._sequence(actual, expected, path, depth)
        else:
            self._record(actual, expected, (actual_names, expected_names), path, depth)

    @override
    def _by_structure(self, actual: object, expected: object, path: str, depth: int, /) -> None:
        """Compare a pair nothing else settled: by kind, then member by member."""
        memo = self.memo
        left = id(actual)
        right = id(expected)
        key = (
            None if self.options.excluded_paths and self._path_bound(path) else (left, right, depth)
        )
        if key is not None and key in memo.settled:
            # Already shown equivalent, at this depth, in this comparison. This is
            # the check that makes the walk cost nodes instead of paths; the
            # reasoning, and the id-reuse hazard it has to survive, are on
            # :class:`Memo`.
            return
        settled = equal_or_unknown(actual, expected)
        if settled is True:
            return
        resolved = self._composite(actual, expected, settled, path, depth)
        if resolved is None:
            return
        marker = (left, right)
        opened = memo.open.get(marker)
        if opened is not None:
            # Both sides are already being compared further up this same stack, so
            # the structures agree exactly as far as they have been walked. Two
            # graphs that cycle in the same shape are equivalent; declaring a
            # difference here would fail every self-referential value there is.
            # It is an *assumption* rather than a result, so say which one was
            # leaned on, and see the closing bookkeeping below for what that costs.
            memo.lean_on(opened)
            return
        position = len(memo.open)
        memo.open[marker] = position
        enclosing = memo.leaned_on
        memo.leaned_on = NOTHING_OPEN
        differences = len(self.findings.items)
        provisional = len(memo.conditional)
        try:
            self._members(actual, expected, resolved, path, depth)
        finally:
            # Discarded rather than left behind: a marker that outlived its frame
            # would make a *later* sibling with a recycled id look like a cycle.
            del memo.open[marker]
        # May this pair's verdict outlive the frame that reached it? Not if the
        # pair turned out to differ -- nothing is remembered in that direction, and
        # everything settled beneath it while assuming it did not has to go with
        # it. Unconditionally if the walk leaned on no open assumption but its own,
        # since finishing clean is what discharges a pair's own assumption, and at
        # that point every verdict recorded beneath is unconditional too.
        # Otherwise the verdict is real but provisional -- it rests on a pair
        # further up the stack that has not finished -- so it is recorded, which is
        # what makes the remaining fields of a node whose child points back at it
        # cost nothing, and its key is remembered for that frame to promote or drop.
        #
        # A frame with **no key of its own** takes neither of those exits. It has
        # none because an exclusion reaches inside it (:meth:`_path_bound`), so
        # finishing clean is not a fact about the pair, it is a fact about the pair
        # *at this path* -- and anything settled below while assuming this frame
        # was equivalent inherited that. Dropping the lot is what keeps the
        # exclusion from leaking: a field excluded at ``a.tag`` lets the frame at
        # ``a`` finish clean, a descendant that points back at ``a`` takes the
        # cycle branch on the strength of it, and without this the verdict that
        # reached would go on to answer for the same pair at ``d.a``, where nothing
        # is excluded and the field disagrees. That is a silent wrong pass, and it
        # is not enough to drop only when this frame is the one discharging the
        # assumption: :meth:`Memo.lean_on` keeps the *shallowest* position leaned
        # on, so a verdict that touched this frame and something above it travels
        # straight past here carrying the higher position. Hence one drop covering
        # both exits, written as the two questions rather than the three outcomes.
        leaned_on = memo.leaned_on
        memo.leaned_on = enclosing
        equivalent = len(self.findings.items) == differences
        outstanding = leaned_on < position
        if equivalent and outstanding:
            memo.lean_on(leaned_on)
        if key is None or not equivalent:
            memo.forget(provisional)
            return
        if outstanding:
            memo.settled[key] = (actual, expected)
            memo.conditional.append(key)
            return
        del memo.conditional[provisional:]
        memo.settled[key] = (actual, expected)
