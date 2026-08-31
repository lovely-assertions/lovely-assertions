"""What one traversal carries, and the two methods the recursion is named by.

The walk is a chain of classes, one link per kind of value it has to take apart,
and this is its root. It holds what every level threads through -- the options,
the memo, the collector the findings go into, the meters that bound the work, and
whether this walk is deciding a pairing rather than describing a graph -- and it
compares nothing itself. Each module below imports its own base and no other
link, which is what keeps the chain a chain rather than a ring of mutual imports.

The order of the links is not a matter of taste: it is the one their own call
graph admits, each calling only what a link above it defines. Two calls cannot be
made to obey that, because the walk is a recursion. Taking a composite apart ends
in asking for a full comparison of each member, and the router that decides what
a value is made of is reached from every kind of value there is -- so both of
those are declared here, without bodies, and implemented at the far end of the
chain, where everything they reach into is already in place.
"""

from typing import override

from lovely_assertions._equivalence._budget import Budget
from lovely_assertions._equivalence._findings import Findings
from lovely_assertions._equivalence._memo import Memo
from lovely_assertions._equivalence._options import Equivalency
from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class WalkState:
    """The state one comparison threads through every level of the walk.

    The root of the chain of walk classes, and the only link in it that compares
    nothing: the options, the memo, the collector and the meters, plus whether
    this walk is deciding a pairing rather than describing a graph. Carrying them
    on the instance is what makes a probe cheap -- order-insensitive pairing
    builds a second walk with a collector of its own and hands it this same memo
    and these same meters, so a probe is another walk over one traversal's state
    rather than a traversal of its own.

    :meth:`compare` and :meth:`_by_structure` are declared here without bodies
    because the chain recurses: every link calls back into the whole walk, and no
    link can name a class defined below it.
    """

    __slots__ = ("budget", "findings", "matching", "memo", "options")

    def __init__(
        self,
        options: Equivalency,
        memo: Memo,
        findings: Findings,
        budget: Budget,
        matching: bool,
        /,
    ) -> None:
        self.options: Equivalency = options
        self.memo: Memo = memo
        self.findings: Findings = findings
        self.budget: Budget = budget
        #: Whether this walk is deciding a pairing rather than describing a graph.
        #: Only a walk that is spends the *comparison* meter -- the scanning one is
        #: charged wherever the cheap pass runs, matching or not, because that pass
        #: runs before the decision to probe is taken.
        self.matching: bool = matching

    @override
    def __repr__(self) -> str:
        return "Walk(" + repr(self.options) + ")"

    def compare(self, actual: object, expected: object, path: str, depth: int, /) -> None:
        """One pair of values at one place in the graph. :class:`Walk` implements it.

        Declared here because this chain is a recursion, and every link in it calls
        back into the whole: a mapping compares its values and a record its fields,
        both by asking for a full comparison rather than a structural one. Naming
        the two entry points once, on the base, is what lets the recursion be
        written as a class per kind of value and still type -- without it a link
        would be calling a method no ancestor of it declares.
        """
        raise NotImplementedError

    def _by_structure(self, actual: object, expected: object, path: str, depth: int, /) -> None:
        """Compare a pair nothing else settled. :class:`StructureWalk` implements it.

        The other half of the same knot, and the reason it is declared rather than
        inherited: the router reaches down to every kind of value, and every kind
        reaches back up to the router.
        """
        raise NotImplementedError
