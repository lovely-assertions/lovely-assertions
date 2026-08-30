"""Finding a run of items inside a longer sequence.

Two questions that look alike and are not: whether the items appear in order with
anything allowed between them, and whether they appear together with nothing
between them. Both apply ``item is target or item == target``, so a value whose
``__eq__`` misbehaves cannot make a sequence fail to contain itself.
"""

from typing import TYPE_CHECKING

from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Sequence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def subsequence_gap(items: "Sequence[object]", wanted: "Sequence[object]", /) -> int | None:
    """Index into ``wanted`` of the first item that breaks the ordered scan.

    ``None`` means every wanted item was found in order, though not necessarily
    adjacent.

    The scan matches on ``item is target or item == target``, the rule ``in``
    itself applies, so ``contains_in_order`` and ``does_not_contain`` cannot
    disagree about whether the sequence holds a NaN.
    """
    position = 0
    count = len(items)
    for index, target in enumerate(wanted):
        while position < count and not (items[position] is target or items[position] == target):
            position += 1
        if position == count:
            return index
        position += 1
    return None


def run_start(items: "Sequence[object]", wanted: "Sequence[object]", /) -> int | None:
    """Index where ``wanted`` appears as an unbroken run, or ``None``.

    An empty ``wanted`` runs at index 0: every sequence contains nothing,
    consecutively.

    Same equality rule as :func:`subsequence_gap`, so the consecutive form
    cannot disagree with the loose one about which items are present either.

    This is the one site that binds the pair to locals before comparing them,
    and the scan is why: every start that does *not* match is rejected by a
    comparison whose identity half fails, so the operands are read twice, and
    here reading one of them means an addition as well as a subscript. Measured,
    the locals pay for themselves here; at the other sites they do not.
    """
    span = len(wanted)
    for start in range(len(items) - span + 1):
        offset = 0
        while offset < span:
            item = items[start + offset]
            target = wanted[offset]
            if not (item is target or item == target):
                break
            offset += 1
        if offset == span:
            return start
    return None
