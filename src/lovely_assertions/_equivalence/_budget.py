"""The bounds that stop a comparison without answering it, and the words for saying so.

A bound on how many differences are worth collecting truncates the *report* and
leaves the verdict standing. The bounds here are the other kind: an
order-insensitive pairing that runs out of allowance never matched the items up,
so neither "equivalent" nor "not equivalent" was established and there is no
honest difference to report. That rule -- such a stop leaves as an exception and
is never folded into the findings -- is what this file exists to keep in one
place, along with the allowances, the meter that spends them and the exception
itself.

The allowances are constants and no option reaches them. A caller who could raise
one could hang a test run, which is the thing being prevented; the remedy the
message offers is to compare fewer items, not to pay more.

The messages are built on the way out and nowhere else, so a pairing that
finishes pays a subtraction and a test against zero and nothing besides. The
message for a walk that exhausted the interpreter's stack keeps them company
because it answers the same question in the other case: that walk also stopped
without finishing, and its caller is owed the same explanation and its own list
of what to do instead.
"""

from typing import Final, override

from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Nodes the engine will visit while *deciding* how unordered items line up,
#: across one whole comparison. Structural pairing is quadratic in full recursive
#: comparisons, and every one of those may itself be a quadratic pairing one level
#: down -- two levels of a hundred unhashables against a hundred is a hundred
#: million comparisons and a test run that looks hung. Only matching spends it:
#: the caller's own walk is never cut short, and what keeps *it* finite is
#: :class:`Memo` rather than an allowance.
#:
#: This is the *only* bound on structural pairing, and a per-level cap on unpaired
#: items is deliberately not a second one. Such a cap is not a bound at all, since
#: levels multiply -- which is exactly what this allowance is for -- and it clips
#: comparisons this allowance pays for comfortably: three hundred genuinely
#: unpaired items on each side is ninety thousand probes and an honest answer.
_MAX_MATCHING: Final = 100_000


#: ``==`` calls the *cheap* half of unordered pairing will spend on items that
#: nothing hashable can stand for, across one whole comparison. Those items are
#: paired by linear scan -- the treatment ``_diff._tally``/``_diff._take`` give the
#: same problem -- which is quadratic in ``==`` rather than in recursive walks. One
#: such call is two or three orders of magnitude cheaper than a node of
#: :data:`_MAX_MATCHING`'s currency, hence the far larger allowance: it pairs off
#: thousands of shuffled records against thousands, in a fraction of a second,
#: without the structural pass being asked for anything at all.
_MAX_SCANNING: Final = 5_000_000


#: The two currencies :class:`Budget` is spent in, named for the message a
#: :class:`TruncatedError` carries. Constants because a message must not be assembled
#: on a path a passing comparison takes.
_MATCHING_NOUN: Final = "comparisons"


_SCANNING_NOUN: Final = "equality checks between items that cannot be hashed"


class TruncatedError(Exception):
    """Raised, and never caught, when a bound stops the pairing of unordered items.

    The one thing this module must not do is hand back a *verdict* it did not
    establish, and pairing that ran out of allowance is exactly that. Reporting it
    as a difference is not symmetric between the two assertions built on top of
    :func:`compare`: a difference makes ``is_equivalent_to`` fail and makes
    ``is_not_equivalent_to`` **pass**, so the same truncation is a wrong failure in
    one direction and a silent wrong pass in the other. Returning ``""`` is worse
    still, and there is no third value a ``str`` can carry.

    So it leaves as an exception, which both directions see identically, and
    :func:`compare` turns it into a :class:`ValueError` -- the same class of answer
    the module already gives a call it cannot serve (see :func:`require_options`).
    A caller who hits it has asked for an order-insensitive comparison of more
    items than the engine will pair up, and the message says so and says what to do
    instead.

    An ``Exception`` rather than a ``BaseException``: no ``except Exception`` in the
    engine sits between the two ``spend`` methods below and the handlers in
    :func:`compare` and :func:`differs` that are meant to see this. The guards that
    do exist wrap a caller's own code -- a comparator, an ``__eq__``, a ``repr`` --
    and none of them encloses a ``spend``.
    """

    __slots__ = ()


def out_of_stack(depth: int, /) -> str:
    """Why a comparison that ran out of stack is not a verdict. Failure path only."""
    return (
        "comparing these two graphs used up the interpreter's stack before the walk finished,"
        " so it was stopped rather than answered: an unfinished comparison is not a verdict,"
        " in either direction. The walk was allowed to descend "
        + str(depth)
        + " levels. Lower that with with_max_depth(), compare a smaller part of the graph, or"
        " raise the interpreter's own limit with sys.setrecursionlimit()."
    )


def _stopped(allowance: int, noun: str, /) -> str:
    """Why the comparison stopped, and what to do about it. Failure path only."""
    return (
        "matching the items of an unordered comparison needed more than "
        + str(allowance)
        + " "
        + noun
        + ", so it was stopped rather than answered: an unfinished pairing is not a"
        + " verdict, in either direction. Compare fewer items in one call. A sequence"
        + " is matched this way only under ignoring_order(); without it its items are"
        + " matched by position instead, which is linear. A set is matched this way"
        + " whatever the options say, so there fewer items is the only remedy."
    )


class Budget:
    """What one comparison may still spend pairing unordered items up.

    Shared by every walk of that comparison, probes included, because the quantity
    worth bounding is the *total*: a hundred items against a hundred is ten
    thousand structural matches at one level, and each of those may itself be a
    hundred-against-a-hundred match one level down. A per-level cap does not bound
    that, and the shape it fails on -- shuffled rows of shuffled cells -- is an
    ordinary thing to write.

    Two meters rather than one, because pairing is spent in two currencies that
    differ by three orders of magnitude a call: :data:`_MAX_MATCHING` counts nodes
    visited inside a structural probe, :data:`_MAX_SCANNING` counts the ``==``
    calls the cheap pass spends on items that cannot be hashed. A single allowance
    covering both would either strangle the cheap pass or fail to bound the
    expensive one. They live on one object so that a walk carries one of these
    rather than two.

    The allowances are read from the module rather than passed in, because there is
    exactly one budget shape and a constructor that could be handed another would
    let a message name a bound that was not the one enforced.

    Spent by pairing alone, and this class is not what bounds the rest. Cutting
    the caller's own walk short would be a wrong failure on honest data, so what
    keeps that walk finite is :class:`Memo`, which remembers the pairs it has
    already settled and so costs the *nodes* of the two graphs rather than the
    paths through them. That distinction is the whole bound: "linear in the graph"
    is not one, because a handful of objects whose every field points at a shared
    child have paths that multiply level by level, and the comparison that walks
    all of them takes minutes on default options while **passing**.
    """

    __slots__ = ("comparisons", "scans")

    def __init__(self) -> None:
        self.comparisons: int = _MAX_MATCHING
        self.scans: int = _MAX_SCANNING

    @override
    def __repr__(self) -> str:
        return (
            "Budget(" + str(self.comparisons) + " comparisons, " + str(self.scans) + " scans left)"
        )

    def spend_comparison(self) -> None:
        """Charge one node of one structural probe.

        The subtraction is the whole of the happy path; the message is built on the
        way out, and never for a comparison that finishes.
        """
        self.comparisons -= 1
        if self.comparisons < 0:
            raise TruncatedError(_stopped(_MAX_MATCHING, _MATCHING_NOUN))

    def spend_scans(self, cost: int, /) -> None:
        """Charge the ``==`` calls one linear scan over unhashable items just cost."""
        self.scans -= cost
        if self.scans < 0:
            raise TruncatedError(_stopped(_MAX_SCANNING, _SCANNING_NOUN))
