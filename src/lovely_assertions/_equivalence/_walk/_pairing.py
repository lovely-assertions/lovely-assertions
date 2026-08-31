"""Matching items that have no position: sets, and sequences under ``ignoring_order()``.

Everywhere else the walk *describes* a pair: it compares, and records what it
finds. Here it also *asks*. Whether two items are equivalent is the input to a
decision about which item pairs with which, and the findings a probe produces are
thrown away once the answer is read off them. That inversion is what earns the
file its own place -- the probes run on a walk of their own, collecting a single
finding and marked as matching so the budget knows to charge them for the
quadratic work they are.

The cheap half of the same problem lives in
:mod:`lovely_assertions._equivalence._leftovers`: equality pairs off whatever it
can, and only what neither side matched arrives here, where every remaining item
costs a full recursive comparison against every remaining candidate. What this
module then does with those leftovers is greedy rather than optimal, for the
reason on :meth:`PairingWalk._pair_up`.

The set branch sits here rather than with the other kinds of value because a set
*is* this problem -- it has no position to compare by, whatever the options say --
while a sequence arrives only when the caller has asked for it.
"""

from lovely_assertions._equivalence._findings import Findings, items_difference, note_difference
from lovely_assertions._equivalence._leftovers import equality_leftovers
from lovely_assertions._equivalence._reading import safe_list, stably_ordered
from lovely_assertions._equivalence._walk._mapping import MappingWalk
from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class PairingWalk(MappingWalk):
    """The link that pairs items off when their order is not to be compared.

    An ancestor of :class:`SequenceWalk`, which hands it a sequence whole the
    moment ``ignoring_order()`` says the positions are not data; :meth:`_set` is
    here for the same reason, one kind of value away from its neighbours. It is
    also the only link that builds a second walk, and :meth:`_matches` says why
    that one is reached through ``type(self)`` rather than by name.
    """

    __slots__ = ()

    def _matches(self, actual: object, expected: object, depth: int, /) -> bool:
        """Whether two items are equivalent, without recording why they are not.

        The same walk with a collector that holds one finding: it stops at the
        first disagreement, which is all a pairing decision needs. The memo is
        shared, because this is still the same traversal -- so a pair a probe has
        already settled costs the next probe nothing -- and so is the budget,
        because this is the work its meters exist to bound.

        There is no such thing here as a probe cut short. A budget that runs out
        raises out of the whole comparison (see :class:`TruncatedError`), so every
        answer this returns is one a finished walk gave -- rather than a maybe that
        the caller above would have to read as a no.
        """
        findings = Findings(1)
        # ``type(self)`` rather than the class by name: this link sits below
        # :class:`Walk` in the chain, and naming it here is the one edge that would
        # turn the chain back into a cycle. There is only ever one concrete walk.
        type(self)(self.options, self.memo, findings, self.budget, True).compare(
            actual, expected, "", depth + 1
        )
        return not findings.items

    def _first_match(self, candidates: list[object], item: object, depth: int, /) -> int | None:
        """Where in ``candidates`` an item equivalent to ``item`` sits, if anywhere."""
        for index, candidate in enumerate(candidates):
            if self._matches(candidate, item, depth):
                return index
        return None

    def _pair_up(self, surplus: list[object], absent: list[object], depth: int, /) -> list[object]:
        """Match each absent item against a surplus one, consuming as it goes.

        Greedy rather than optimal: finding the best overall pairing is an
        assignment problem, and the answer it would change is which of two equally
        unmatched items gets reported. ``surplus`` is edited in place, so what is
        left in it afterwards is what nothing matched.
        """
        unmatched: list[object] = []
        for item in absent:
            index = self._first_match(surplus, item, depth)
            if index is None:
                unmatched.append(item)
            else:
                del surplus[index]
        return unmatched

    def _unordered(
        self, actual_items: list[object], expected_items: list[object], path: str, depth: int, /
    ) -> None:
        """Pair items up in any order: cheaply by equality, then by comparison.

        The two passes are not an optimisation on top of one algorithm, they are
        the algorithm. Structural pairing is quadratic *in full recursive
        comparisons*, so anything equality can settle has to be settled by equality
        first; what survives is the handful that genuinely needs comparing.

        The cheap pass pairs unhashable items too, which is what lets a shuffled
        list of JSON records come back equivalent at all: a ``dict`` has no hash,
        so without a surrogate for it (see :func:`_stand_in`) every record arrives
        at the structural pass unpaired and the whole comparison is spent there.
        """
        surplus, absent = equality_leftovers(actual_items, expected_items, self.budget)
        if not surplus and not absent:
            return
        absent = self._pair_up(surplus, absent, depth)
        if absent:
            self.findings.add(items_difference(path, "missing items:", stably_ordered(absent)))
        if surplus:
            self.findings.add(items_difference(path, "extra items:", stably_ordered(surplus)))

    # -- sets ---------------------------------------------------------------
    def _set(self, actual: object, expected: object, path: str, depth: int, /) -> None:
        """A set has no position to report, so it is matched the unordered way.

        Items that are simply equal pair off through the hash the set is built on,
        which is the comparison a set already makes; anything left is matched
        structurally, so a set of records still honours the options.
        """
        actual_items = safe_list(actual)
        expected_items = safe_list(expected)
        if actual_items is None or expected_items is None:
            self.findings.add(note_difference(path, "the items of this set could not be read"))
            return
        self._unordered(actual_items, expected_items, path, depth)
