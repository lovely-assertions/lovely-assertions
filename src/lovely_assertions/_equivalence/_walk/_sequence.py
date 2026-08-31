"""Sequences: index against index, and what a surplus tail is reported as.

A sequence is the one kind of value whose member names are positions, and that
decides both halves of this file. The comparison walks the shared prefix, because
index against matching index is what a list means. The report is two findings
rather than one, because two sequences of different lengths differ in a count
*and* in a place, and everything else this engine reports names a place.

What is deliberately not here is the other reading of the same pair.
``ignoring_order()`` says the positions are not data, at which point a sequence is
the same problem as a set, so it is handed to the pairing link rather than
answered here.
"""

from lovely_assertions._equivalence._findings import items_difference, note_difference
from lovely_assertions._equivalence._paths import index_path
from lovely_assertions._equivalence._reading import safe_list
from lovely_assertions._equivalence._walk._pairing import PairingWalk
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._text import count_of

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class SequenceWalk(PairingWalk):
    """The link that compares two sequences position by position.

    A subclass of :class:`PairingWalk` because the one reading it does not do
    itself -- order-insensitive matching -- is that link's, and an ancestor of the
    router, which is what decides a pair is a sequence at all. Its own descent
    goes back through :meth:`compare`: an item of a sequence is an ordinary pair
    and gets the ordinary treatment, options, memo and all.
    """

    __slots__ = ()

    # -- sequences ----------------------------------------------------------
    def _sequence(self, actual: object, expected: object, path: str, depth: int, /) -> None:
        """Position by position, unless the caller opted out of order."""
        actual_items = safe_list(actual)
        expected_items = safe_list(expected)
        if actual_items is None or expected_items is None:
            self.findings.add(note_difference(path, "the items of this sequence could not be read"))
            return
        if self.options.ignore_order:
            self._unordered(actual_items, expected_items, path, depth)
            return
        shared = min(len(actual_items), len(expected_items))
        for index in range(shared):
            if self.findings.full:
                return
            child = index_path(path, index)
            if not self._selects(None, child):
                continue
            self.compare(actual_items[index], expected_items[index], child, depth + 1)
        if len(actual_items) == len(expected_items):
            return
        self.findings.add(
            note_difference(
                path,
                "lengths differ: "
                + count_of(len(actual_items), "item")
                + ", expected "
                + str(len(expected_items)),
            )
        )
        # Reported at the first index with no counterpart rather than at the
        # sequence itself: a surplus item has a *where*, and every other finding
        # this engine produces names one. The length line above is the summary;
        # this is the location.
        tail = index_path(path, shared)
        if len(actual_items) > shared:
            self.findings.add(items_difference(tail, "extra items:", actual_items[shared:]))
        if len(expected_items) > shared:
            self.findings.add(items_difference(tail, "missing items:", expected_items[shared:]))
