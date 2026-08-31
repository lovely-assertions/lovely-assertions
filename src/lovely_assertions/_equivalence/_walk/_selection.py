"""What a descent asks first: whether a member is in scope, and whether a pair has parts to walk.

``excluding``, ``including`` and ``excluding_path`` are read here and nowhere
else in the walk -- the router only tests whether there is an excluded path at
all, to skip the call to :meth:`SelectingWalk._path_bound` when there is not. A
record's field, a mapping's key and a sequence's position all pass through the
same predicate, so a member is skipped identically wherever it is reached rather
than through a branch per kind that would have to be kept in step with the
others.

The two other questions a descent needs settled first keep it company. Whether an
excluded path reaches into this branch is what decides if a verdict about this
pair may be remembered at all -- a question about the options, not about the two
values. And whether a pair equality did not settle has any members to take apart
is decided by classifying the two values and testing the depth bound, without
descending into either; when the answer is no, the reason there is nothing to
walk is itself the finding.

Which is also why this link sits where it does. Everything here is answered from
the options, the two values and the depth, and none of it calls a method a link
below defines, so it is the first the chain's own call graph admits above the
state they all read.
"""

from lovely_assertions._equivalence._classification import KIND_LEAF, classify
from lovely_assertions._equivalence._findings import pair_difference, types_difference
from lovely_assertions._equivalence._paths import path_excluded
from lovely_assertions._equivalence._rendering import leaf_difference
from lovely_assertions._equivalence._walk._state import WalkState
from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class SelectingWalk(WalkState):
    """The walk's selection rules, and the check for a pair with nothing to walk.

    The first link above :class:`WalkState`, and it can be first because it
    reaches downwards for nothing: :meth:`_selects` is asked by the links that
    walk members by name or by position, :meth:`_path_bound` and :meth:`_composite`
    by the router that dispatches to them, and none of the three calls anything
    those links define.
    """

    __slots__ = ()

    # -- selection ----------------------------------------------------------
    def _selects(self, name: str | None, path: str, /) -> bool:
        """Whether a member with this name, at this path, is compared at all.

        ``name`` is ``None`` for a member that has none -- an index, a mapping key
        that is not a string. Those are unreachable by ``excluding``/``including``
        and are selected by path alone.
        """
        options = self.options
        if name is not None:
            if name in options.excluded_names:
                return False
            if options.included_names and name not in options.included_names:
                return False
        return not path_excluded(path, options.excluded_paths)

    def _path_bound(self, path: str, /) -> bool:
        """Whether what is under this path depends on *where* this path is.

        A verdict may be remembered under a key that says nothing about where the
        pair was reached only if where it was reached cannot change it. One option
        makes it change: :meth:`Equivalency.excluding_path` names a branch, so the
        same two objects can be equivalent under one parent and not under another.

        The test is deliberately conservative and cheap. If no excluded path even
        starts with this one, nothing under here can be excluded and the verdict is
        about the pair alone. If one does, this subtree is walked afresh every time
        it is reached -- the slow answer, and the right one. Excluding a path
        therefore costs the memo only for the branch it names, rather than turning
        it off for the whole comparison, which would let one option bring back the
        shape that hangs.

        **A yes here has to reach further than this pair**, or it is a silent wrong
        pass. Withholding a key from *this* frame is not enough, because a frame an
        exclusion reaches into can finish clean **because** of the exclusion; a
        descendant that points back at it
        then takes the cycle branch on the strength of that, and the verdict it
        reaches is contingent on where it was reached from even though its own path
        is nowhere near an exclusion. So :meth:`_by_structure` also drops, rather
        than keeps, everything settled beneath a frame this returns ``True`` for.
        Conservative again: some of what it drops was sound.

        Asked only when there is an exclusion to ask about; the caller guards the
        call, so an ordinary comparison never makes it.
        """
        for candidate in self.options.excluded_paths:  # noqa: SIM110  (a generator expression would allocate)
            if candidate.startswith(path):
                return True
        return False

    def _composite(
        self, actual: object, expected: object, settled: bool | None, path: str, depth: int, /
    ) -> tuple[str, tuple[str, ...], tuple[str, ...]] | None:
        """The kind and names to walk this pair by, or ``None`` when there is nothing to walk.

        Three ways a pair that equality did not settle still has no members to walk:
        the two values are of different kinds, they are both leaves, or the walk has
        reached the depth bound. Each records its own finding, because in each case
        the reason there is nothing to take apart **is** the finding.

        Split out of :meth:`_by_structure` so that the memo bookkeeping around the
        descent reads as one thing rather than as the tail of a list of special
        cases. Called before the descent and returned from before it, so it costs no
        stack while the walk is deep -- and not called at all for the commonest node
        of a passing comparison, the pair ``==`` agrees on.
        """
        actual_kind, actual_names = classify(actual)
        expected_kind, expected_names = classify(expected)
        if actual_kind != expected_kind:
            self.findings.add(types_difference(path, actual, expected))
            return None
        if actual_kind == KIND_LEAF:
            self.findings.add(leaf_difference(path, actual, expected, settled))
            return None
        if depth >= self.options.max_depth:
            self.findings.add(
                pair_difference(
                    path,
                    actual,
                    expected,
                    "(not taken apart: the maximum depth of "
                    + str(self.options.max_depth)
                    + " stops here)",
                )
            )
            return None
        return (actual_kind, actual_names, expected_names)
