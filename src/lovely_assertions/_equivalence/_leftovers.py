"""The cheap half of order-insensitive matching, and the leftovers it hands on.

Comparing two collections without regard to order -- a ``set``, or a sequence
under ``ignoring_order()`` -- is a multiset difference, and the expensive way to
compute one is to compare every item against every other item structurally. So
this module computes it by ``==`` first and gives the walk back only what neither
side matched: the items the actual value carried that nothing wanted, and the
items the expectation named that nothing supplied. Equality is sound in that
direction for every option that only ever *widens* what counts as equivalent, and
all but two do: a pair ``==`` has already settled needs no comparison at all. The
two that can be narrower -- a hand-written comparator, and
``comparing_enums_by_name()`` on members of different classes that share a value
-- are never asked about a pair this pass has paired off, so an item matched here
is matched on Python's terms rather than the configuration's.

Two pools, because Python has two kinds of item. Anything hashable pairs off
through a dictionary in linear time; anything else is kept aside and paired by
linear scan, charged to the budget's scanning meter so that the quadratic case is
bounded across the whole comparison. What earns this its own module is what sits
between the two: a ``dict`` and a ``list`` have no hash and are the ordinary shape
of a JSON payload, so a surrogate is canonicalised for each -- tagged by kind,
bounded in depth, and equal to another surrogate exactly when the two values are
-- which moves the commonest unordered comparison out of the scan and into the
pool. Without it a few thousand shuffled records against a few thousand exhaust
the scanning allowance and the comparison is refused rather than answered.

That canonicalisation has to be sound rather than merely fast, which is why it is
kept together with the matching it serves and nowhere near the rest of the walk.
Everywhere else in the engine a pair the cheap pass misses costs a slower
comparison and nothing more; a pair it matches *wrongly* is dropped here and never
reaches the structural pass, so it is a wrong verdict. Hence exact types rather
than ``isinstance``, and a sentinel rather than a guess for a value nothing can
stand for.

Nothing here knows about the options, the findings or the paths. It is handed two
lists of items and a budget, and answers with two lists of items.
"""

from typing import TYPE_CHECKING, Final, cast

from lovely_assertions._equivalence._budget import Budget
from lovely_assertions._equivalence._reading import equal_or_unknown
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Iterable

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Returned by :func:`_stand_in` for a value nothing hashable can stand for.
_NO_STAND_IN: Final = object()


#: How deep :func:`_stand_in` will canonicalise before giving up.
#:
#: A record nested past this keeps the linear scan instead: correct, just slower.
#: Four levels reaches the values inside a list of records holding a list of
#: records, which is as deep as the shape this is for usually goes.
_MAX_STAND_IN_DEPTH: Final = 4


def _frozen_parts(values: "Iterable[object]", depth: int, /) -> "tuple[object, ...] | None":
    """Each value's surrogate in order, or ``None`` if any of them has none."""
    parts: list[object] = []
    for held in values:
        surrogate = _stand_in(held, depth)
        if surrogate is _NO_STAND_IN:
            return None
        parts.append(surrogate)
    return tuple(parts)


def _stand_in(value: object, depth: int = 0, /) -> object:
    """A hashable surrogate, equal to another exactly when the values are.

    ``dict`` and ``list`` have no hash, so without this a shuffled list of JSON
    records -- the ordinary shape of a payload anyone asserts on -- pairs off by
    linear scan alone. That is quadratic in ``==``, and a few thousand records
    against a few thousand exhaust the scanning allowance before an answer is
    reached, so the comparison is refused outright.

    The surrogate makes them poolable. For a ``dict`` it is the frozen set of its
    keys paired with its values' own surrogates, which is equal for two dicts
    exactly when the dicts are, because a mapping's keys are unique and hashable by
    its own invariant. For a ``list`` it is the tuple of its items' surrogates. Each
    carries a tag, so a list can never pair with the tuple holding the same items --
    ``[1, 2] != (1, 2)``, and a surrogate that disagreed with ``==`` on one pair
    would not be sound on any.

    ``type(value) is`` rather than ``isinstance``: a ``dict`` subclass, an
    ``OrderedDict``, a ``list`` subclass keeps the scan. Canonicalising those would
    be correct on equality alone, but a subclass is free to narrow ``__eq__``, and
    this is the one place in the engine where a wrong pair is a wrong *verdict*
    rather than a slower one. They pair against each other by scan exactly as
    before, and against a plain ``dict`` in the structural pass, which is wider
    than ``==`` and is where an unpaired item goes anyway.

    :data:`_NO_STAND_IN` for everything else, including a value that turns out to
    hold something unhashable. That answer costs one failed attempt and then the
    linear scan, so nothing is worse off for the attempt having been made.
    """
    if depth > _MAX_STAND_IN_DEPTH:
        return _NO_STAND_IN
    kind = type(value)
    if kind is dict:
        mapping = cast("dict[object, object]", value)
        parts = _frozen_parts(mapping.values(), depth + 1)
        return _NO_STAND_IN if parts is None else ("d", frozenset(zip(mapping, parts, strict=True)))
    if kind is list:
        parts = _frozen_parts(cast("list[object]", value), depth + 1)
        return _NO_STAND_IN if parts is None else ("l", parts)
    try:
        hash(value)
    except Exception:
        return _NO_STAND_IN
    return ("v", value)


def equality_leftovers(
    actual_items: list[object], expected_items: list[object], budget: Budget, /
) -> tuple[list[object], list[object]]:
    """Pair off items that are simply equal; hand back what neither side matched.

    Equality is used as the cheap half of order-insensitive matching because it is
    sound in the direction that matters: two values that are equal hold the same
    information, so they are equivalent under any configuration that only ever
    *widens* what counts as equivalent -- which all but two options do. A
    hand-written comparator narrower than ``==``, and ``comparing_enums_by_name()``
    where two members of different classes share a value, are not consulted for a
    pair equality has already settled.

    Duplicates are counted: three copies on one side match three on the other and
    no more, which is what makes this a multiset comparison rather than a set one.

    **Two pools, because Python has two kinds of item.** Anything a hashable
    surrogate can stand for pairs through a dictionary in linear time -- which,
    since :func:`_stand_in` covers ``dict`` and ``list``, includes the ordinary
    shape of a JSON payload. What is left has no hash and nothing that can stand
    for one: an object that defines ``__eq__`` and sets ``__hash__`` to ``None``, a
    ``dict`` subclass free to narrow its own equality. Those are kept in a second
    pool and matched by linear scan, exactly the treatment
    ``_diff._sequences._tally``/``_take`` give the same problem. That is quadratic
    in ``==``, and it is charged to the budget's scanning meter so that it is
    bounded across the whole comparison rather than per level.

    Both pools matter to the *answer*, not only to the cost. An item this pass
    leaves unpaired goes to the structural pass, which is quadratic in full
    recursive comparisons and spends the matching allowance; a shuffled list long
    enough to exhaust that allowance would be refused rather than answered, on data
    that is plainly equivalent.
    """
    pool: dict[object, list[int]] = {}
    loose: list[int] = []
    for index, item in enumerate(actual_items):
        surrogate = _stand_in(item)
        if surrogate is _NO_STAND_IN:
            # nothing hashable stands for it; paired by scan
            loose.append(index)
        else:
            pool.setdefault(surrogate, []).append(index)
    taken: set[int] = set()
    absent: list[object] = []
    for item in expected_items:
        position = _take_index(pool, loose, actual_items, item, budget)
        if position is None:
            absent.append(item)
        else:
            taken.add(position)
    surplus = [item for index, item in enumerate(actual_items) if index not in taken]
    return surplus, absent


def _take_index(
    pool: dict[object, list[int]],
    loose: list[int],
    items: list[object],
    item: object,
    budget: Budget,
    /,
) -> int | None:
    """Consume one position holding an item equal to this one; ``None`` when there is none.

    The scan is reached only when *this* item has no hash either, which is what
    keeps a list of ordinary hashables paying nothing for the second pool. A
    hashable item that is ``==`` to an unhashable one -- two classes written to
    compare across that line -- is missed here and picked up by the structural
    pass, which is wider than ``==`` and is where an unpaired item goes anyway.
    """
    surrogate = _stand_in(item)
    # nothing stands for it here either, so scan
    if surrogate is _NO_STAND_IN:
        return _take_loose(loose, items, item, budget)
    positions = pool.get(surrogate)
    if not positions:
        return None
    return positions.pop()


def _take_loose(
    loose: list[int], items: list[object], item: object, budget: Budget, /
) -> int | None:
    """Consume one *unhashable* position equal to this item, by linear scan.

    ``loose`` holds positions rather than items so that the caller can tell which
    of ``items`` was consumed, which is what makes duplicates count on this side
    too. Charged for what the scan actually cost rather than for its worst case:
    over-charging would spend the allowance on comparisons that never happened, and
    the allowance decides whether an honest comparison gets an answer.
    """
    for offset, position in enumerate(loose):
        if equal_or_unknown(items[position], item) is True:
            budget.spend_scans(offset + 1)
            del loose[offset]
            return position
    budget.spend_scans(len(loose))
    return None
