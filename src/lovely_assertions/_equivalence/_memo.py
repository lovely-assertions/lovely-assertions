"""The memory one comparison keeps: what it is in the middle of, and what it finished.

Both are needed and neither can do the other's job. The pairs whose frames are
open right now are what stops a value that contains itself from recursing
forever; the pairs a finished frame proved equivalent are what keeps the walk
costing the number of nodes in the two graphs rather than the number of paths
through them. A cycle stack forgets a pair the moment its frame returns -- exactly
right for the first job and useless for the second -- so :class:`Memo` carries
both, along with the bookkeeping that joins them: a verdict reached while leaning
on a frame that has not finished is not yet a fact, and has to be held until that
frame either discharges it or takes it back.

State, and the two operations that maintain it. No policy: nothing here decides
whether a verdict may be kept, because only the frame that reached it knows
whether it finished clean, so that judgement stays where the walking happens.
Nothing in this file imports another module of the engine either, which is what
lets every part of the walk share one memo without a cycle forming through it.

Two sentinels stand beside the class, each naming an absence that would otherwise
read as an answer: a type nobody has looked at yet, and a frame that leaned on
nothing at all.
"""

from typing import Final, override

from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Stands in for "this type has not been looked at yet" in the engine's per-type
#: cache of what a class declares. A sentinel rather than ``None`` because
#: ``None`` is one of the answers being cached -- "this type declares no fields"
#: -- and a cache that could not tell it from a miss would re-derive it forever,
#: which is the answer the derivation is most expensive to reach.
UNCACHED: Final = object()


#: :attr:`_Memo.leaned_on` when a frame has leaned on no open assumption at all.
#: Larger than any stack position the walk can reach, so that the ordinary
#: ``min``-style comparison against it needs no special case.
NOTHING_OPEN: Final = 1 << 62


class Memo:
    """What one comparison has settled, and what it is still assuming.

    Four fields, and they are one mechanism rather than four.

    ``open`` is the cycle stack: every pair currently being compared, mapped to
    its position in that stack. The position, not merely the membership, is what
    the conditional bookkeeping below needs.

    ``settled`` is what makes the walk affordable. Its entries are the pairs a
    *finished* walk found equivalent, keyed by ``(id(actual), id(expected),
    depth)``. Without it the walk costs the number of **paths** through the two
    graphs rather than the number of nodes, because ``open`` forgets a pair the
    moment its frame returns -- which is exactly right for a cycle memo and useless
    as a visited one. A handful of objects whose every field points at a shared
    child multiply their paths level by level, and the comparison takes minutes on
    default options and then **passes**: a hang, with no message, on a test that
    was about to go green. A parent backref plus a couple of shared configuration
    objects is the same shape and is not exotic.

    Only *equivalent* is remembered. A pair that produced findings is walked again
    wherever it is reached again, so the report still names every place the
    difference occurs; the bound on that direction is :data:`MAX_DIFFERENCES`,
    which stops the whole walk once it has collected its fill.

    ``depth`` is in the key because it is in the answer: the same pair taken apart
    at depth three may, at depth nine, reach :attr:`Equivalency.max_depth` and be
    reported as a pair the walk declined to open. Handing the shallow verdict to
    the deep reach would drop that report, and "I stopped here" is a finding.

    What the memo does to that bound is worth saying plainly, because it is a
    behaviour difference rather than a saving: the depth bound fires less often
    than the shape of the graph alone would suggest. A pair reached twice at the
    same depth is walked once, so a branch reached again by a second route is not
    descended again and cannot run into the bound there. The comparison answers
    "equivalent" where an unmemoised walk would answer "I ran out of levels", which
    is the better of the two answers and is still not the same one. Nothing moves
    in the other direction: a difference is never remembered, so no finding can be
    lost this way.

    **The id-reuse hazard, and what is done about it.** ``open`` may key on bare
    ids because every object in it is a local of a frame further up the stack and
    so cannot be collected. ``settled`` outlives those frames -- that is the whole
    point of it -- so a value built on the way past, a property that returns a
    fresh object each time, could be freed and have its id handed to something
    else, and a later unrelated pair would be declared equivalent without being
    looked at. That is a wrong *pass*, the one failure this module is written to
    avoid. So each entry's value is the pair itself: holding both objects keeps
    the ids that name them unusable by anything else for as long as the entry
    exists. Keying on something stable instead was the alternative and there is no
    such thing -- an unhashable subject has no identity to key on but ``id``.

    ``conditional`` is the part that is not obvious. A frame that took the cycle
    branch answered "equivalent" by *assuming* the pair further up the stack is
    equivalent, and an assumption is not a result. Recording it unconditionally
    would let a probe that later found a difference leave a wrong entry behind for
    a different probe to read. So a verdict reached while leaning on an assumption
    an enclosing frame has not yet discharged is recorded and its key remembered
    here; the enclosing frame promotes the lot when it finishes clean -- its own
    completion is what discharges its assumption -- and :meth:`forget` drops the
    lot when it does not. Keeping the entry rather than refusing to write one is
    what makes the parent-backref shape fast, since every field of a node that
    points back at its parent leans on that parent's assumption.

    ``leaned_on`` is what tells a frame which of the two it is: the shallowest
    still-open position anything beneath it reached for. Shallower than the
    frame's own position means the assumption belongs to a frame further up, so
    the verdict travels upwards as provisional rather than being kept outright.
    """

    __slots__ = ("conditional", "leaned_on", "open", "settled")

    def __init__(self) -> None:
        self.open: dict[tuple[int, int], int] = {}
        self.settled: dict[tuple[int, int, int], tuple[object, object]] = {}
        self.conditional: list[tuple[int, int, int]] = []
        #: The shallowest still-open assumption the current frame has leaned on.
        self.leaned_on: int = NOTHING_OPEN

    @override
    def __repr__(self) -> str:
        return "Memo(" + str(len(self.open)) + " open, " + str(len(self.settled)) + " settled)"

    def lean_on(self, position: int, /) -> None:
        """Record that the assumption open at ``position`` was leaned on."""
        self.leaned_on = min(self.leaned_on, position)

    def forget(self, mark: int, /) -> None:
        """Drop every conditional verdict recorded since ``mark``.

        Called when a frame's own verdict cannot be kept -- the pair turned out to
        differ, or an exclusion reached inside it, so finishing clean was a fact
        about the pair *at that path* rather than about the pair. Either way every
        answer beneath it that leaned on it is unmade with it. The spans nest, so a
        slice off the end is exactly the set to drop.
        """
        conditional = self.conditional
        settled = self.settled
        while len(conditional) > mark:
            del settled[conditional.pop()]
