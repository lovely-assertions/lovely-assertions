"""Position first, then length, then membership -- in that order, deliberately.

Two sequences that differ at index three have one useful thing to say, and it is
not that they are both of length ten. Only once no position disagrees does the
length matter, and only once the lengths agree does it become interesting that
the same items are present in a different arrangement.

The NamedTuple case breaks that order on purpose. Both sides agreeing on field
names means the reader thinks in names, not indices, so the record describer
answers instead -- ``.retries`` says more than ``[2]`` about the same slot.
"""

from collections.abc import Sequence
from typing import Final

from lovely_assertions._diff._fields import field_lines
from lovely_assertions._diff._primitives import equal, indentation
from lovely_assertions._diff._render import membership_lines, pair_lines
from lovely_assertions._diff._type_notes import type_note
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._reflection import named_tuple_field_names
from lovely_assertions._text import count_of

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Unhashable items tolerated before the multiset comparison gives up. Matching
#: them is quadratic and this runs while a test is already failing, so the worst
#: case stays bounded; the positional findings are reported either way.
_MAX_UNHASHABLE: Final = 100


def describe_sequence_or_record(
    actual: Sequence[object], expected: Sequence[object], depth: int, /
) -> list[str]:
    """Field names when both tuples agree on them, indices otherwise.

    A NamedTuple **is** a tuple, so the sequence describer claims it happily and
    reports "index 0" for a field the reader calls ``x`` and has never indexed by
    hand. The names are the better label -- but only while *both* sides declare
    the same ones.

    That condition is not fussiness. ``tuple.__eq__`` ignores the class, so
    ``Point(1, 2) == Coord(1, 2)`` is true: for two tuples with different names,
    or with none on one side, the values are what parted company and the indices
    are the only label both sides share. Naming the two *types* instead would be
    an account of the failure that is not true, and labelling one side's values
    with the other side's names would be worse. The names are also dropped when
    reading them yields nothing -- a tuple subclass is free to declare a
    ``_fields`` it does not carry, and an index diff beats an empty block.
    """
    names = named_tuple_field_names(actual)
    if names and names == named_tuple_field_names(expected):
        lines = field_lines(actual, expected, names, names, depth)
        if lines:
            return lines
    return _describe_sequence(actual, expected, depth)


def _describe_sequence(
    actual: Sequence[object], expected: Sequence[object], depth: int, /
) -> list[str]:
    """Position first, then length, then what is surplus and what is absent.

    Order is what a sequence *is*, so the first line names an index. The set
    arithmetic comes after it and only when it adds something: for two lists that
    differ in one slot, "missing" and "extra" would just repeat the position line
    in a form that no longer says where.
    """
    indent = indentation(depth)
    index = _first_difference(actual, expected)
    lines: list[str] = []
    if index is not None:
        lines.extend(
            pair_lines(
                "first difference at index " + str(index), actual[index], expected[index], depth
            )
        )
    if len(actual) != len(expected):
        lines.append(
            indent
            + "lengths differ: "
            + count_of(len(actual), "item")
            + ", expected "
            + str(len(expected))
        )
    lines.extend(_sequence_membership(actual, expected, index, indent))
    if lines:
        return lines
    return type_note(actual, expected, "items", depth)


def _sequence_membership(
    actual: Sequence[object], expected: Sequence[object], index: int | None, indent: str, /
) -> list[str]:
    """Which items are surplus and which are absent, duplicates counted.

    Silent in the two cases where it would mislead: when the answer only echoes
    the differing position, and when the items cannot be matched cheaply -- see
    :func:`_unmatched`, which would rather say nothing than hang.
    """
    missing = _unmatched(expected, actual)
    extra = _unmatched(actual, expected)
    if missing is None or extra is None:
        return []
    if not missing and not extra:
        if index is None or len(actual) != len(expected):
            return []
        return [indent + "the same items, in a different order"]
    if index is not None and missing == [expected[index]] and extra == [actual[index]]:
        return []
    return membership_lines(indent, missing, extra, "items")


def _first_difference(actual: Sequence[object], expected: Sequence[object], /) -> int | None:
    """Index of the first item that differs, ignoring any length mismatch."""
    for index in range(min(len(actual), len(expected))):
        if not equal(actual[index], expected[index]):
            return index
    return None


def _unmatched(items: Sequence[object], against: Sequence[object], /) -> list[object] | None:
    """Items of ``items`` that ``against`` has no counterpart for, duplicates counted.

    ``None`` when the answer would cost more than it is worth. Hashable items are
    matched through a tally; unhashable ones -- a list of dicts is an ordinary
    subject -- fall back to a linear scan, which is quadratic overall, so past
    :data:`_MAX_UNHASHABLE` of them this declines to answer instead of hanging a
    test run that is already red.
    """
    tally = _tally(against)
    if tally is None:
        return None
    counts, unhashable = tally
    # The filter consumes as it goes: `_take` removes the counterpart it matched,
    # so three copies of an item in `items` only match three copies in `against`.
    return [item for item in items if not _take(item, counts, unhashable)]


def _tally(items: Sequence[object], /) -> tuple[dict[object, int], list[object]] | None:
    """Count the hashable items, list the rest; ``None`` past the unhashable cap."""
    counts: dict[object, int] = {}
    unhashable: list[object] = []
    for item in items:
        try:
            counts[item] = counts.get(item, 0) + 1
        except TypeError:
            if len(unhashable) == _MAX_UNHASHABLE:
                return None
            unhashable.append(item)
    return counts, unhashable


def _take(item: object, counts: dict[object, int], unhashable: list[object], /) -> bool:
    """Consume one occurrence of ``item``; ``False`` when there is none left."""
    try:
        remaining = counts.get(item, 0)
    except TypeError:
        for index, candidate in enumerate(unhashable):
            if equal(candidate, item):
                del unhashable[index]
                return True
        return False
    if remaining == 0:
        return False
    counts[item] = remaining - 1
    return True
