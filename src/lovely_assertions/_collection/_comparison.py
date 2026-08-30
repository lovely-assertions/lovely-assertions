"""The questions a container will not answer on its own.

All of these run on the happy path, which is the whole reason they read the way
they do: no message is built, nothing is allocated that is not needed to answer,
and each returns as soon as the answer is settled rather than finishing the walk.

A ``Collection`` promises ``__contains__``, ``__iter__`` and ``__len__`` and
nothing else. Everything an assertion here wants to know beyond those three has
to be worked out, and worked out without assuming the items hash or order.
"""

from typing import TYPE_CHECKING, Any

from lovely_assertions._collection._hashing import searchable
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Sequence, Sized

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


# ---------------------------------------------------------------------------
# Comparison helpers -- these run on the happy path, so they allocate nothing
# beyond what the question itself requires.
# ---------------------------------------------------------------------------
def is_none_or_empty(subject: "Sized | None", /) -> bool:
    """Whether the subject is missing entirely or simply holds nothing.

    Declared as an optional parameter so the ``None`` branch is honest to both
    checkers: ``CollectionExpect``'s subject type excludes ``None``, and a
    comparison against it inside the method would be flagged as unreachable.
    """
    return subject is None or len(subject) == 0


def count_equal(candidates: "Collection[Any]", value: object, /) -> int:
    """How many of ``candidates`` count as ``value``. Runs whether or not it fails.

    ``x is y or x == y``, Python's own membership rule -- the comparison ``in``
    makes item by item, and the one ``_mapping`` spells out at each of its sites
    for the same reason: equality alone would report a NaN a collection
    demonstrably holds as absent, so an occurrence count and a plain ``contains``
    would answer one question two ways.

    Spelled as a loop rather than ``sum(1 for ...)``: the generator expression is
    an allocation, and this runs on the *passing* side of every occurrence-
    constrained assertion, which is required to allocate nothing. Walking is also
    the only implementation available -- ``__contains__`` answers whether, never
    how many -- so a ``set`` pays a scan here where an unconstrained ``contains``
    pays a hash lookup.
    """
    count = 0
    for candidate in candidates:
        if candidate is value or candidate == value:
            count += 1
    return count


def none_outside(items: "Collection[object]", container: "Collection[object]", /) -> bool:
    """Whether every one of ``items`` is in ``container``.

    Spelled as a loop rather than ``all(item in holder for item in items)``
    because this runs on the happy path: the generator expression the tidier
    spelling needs is an allocation on every *passing* assertion, and a passing
    assertion is required to allocate nothing at all.

    :func:`searchable` decides whether the membership test is answered by a scan
    or by a hash table, and answers the same question either way -- see its
    docstring for what "the same question" is doing there, because a set is not a
    drop-in for ``in`` and the cases where it is not are the interesting ones.
    """
    holder = searchable(items, container)
    for item in items:  # noqa: SIM110  (a generator expression would allocate)
        if item not in holder:
            return False
    return True


def any_inside(items: "Collection[object]", container: "Collection[object]", /) -> bool:
    """Whether at least one of ``items`` is in ``container``.

    Spelled as a loop rather than ``any(item in holder for item in items)``
    for the reason :func:`none_outside` is: the generator expression is an
    allocation on every *passing* assertion, and those must allocate nothing.

    One helper serves both call shapes -- ``intersects(other)`` and
    ``contains_any(*items)`` ask the same question of the same two collections --
    so the two assertions can word their failures differently and cannot disagree
    about the answer.

    Through :func:`searchable`, like its mirror. The table is built up front even
    though this can return on the first item, which is the right way round: the
    call that returns early is the *cheap* one, and the call that has to look at
    everything -- ``does_not_intersect`` over two long lists, which succeeds only
    by finding nothing -- is the one that would otherwise be quadratic.
    """
    holder = searchable(items, container)
    for item in items:  # noqa: SIM110  (a generator expression would allocate)
        if item in holder:
            return True
    return False


def first_repeat(
    items: "Collection[Any]", key: "Callable[[Any], object] | None" = None, /
) -> tuple[object, int] | None:
    """The first value that has already been seen, with where it was, or ``None``.

    The *value* is the item itself, or what ``key`` makes of it -- which is what
    a keyed failure has to name, since the two rows that collided are different
    objects and only their ids are the finding.

    Hashable values go through a ``set``; the moment one is not hashable the scan
    falls back to a linear comparison for it, because a collection of dicts is an
    ordinary test subject and refusing to check it would be worse than being slow.

    The value comes back alongside its position because an unordered subject
    cannot be asked for it afterwards -- there is no ``items[index]`` to go back
    to.
    """
    seen: set[object] = set()
    unhashable: list[object] = []
    for index, item in enumerate(items):
        value = item if key is None else key(item)
        try:
            if value in seen:
                return value, index
            seen.add(value)
        except TypeError:
            if value in unhashable:
                return value, index
            unhashable.append(value)
    return None


def unmatched_predicate(
    items: "Collection[Any]", predicates: "Sequence[Callable[[Any], bool]]", /
) -> int | None:
    """Index of the first predicate no *distinct* item can be assigned to.

    Kuhn's augmenting-path matching, not one ``any()`` per predicate: given items
    ``[1, 2]`` and predicates ``is_one_or_two, is_one``, the independent test
    passes both and the assignment is still impossible -- ``is_one_or_two`` has
    taken the only item ``is_one`` can use. Augmenting lets it hand that item
    back when it has somewhere else to go.
    """
    owner: list[int | None] = [None] * len(items)
    for index in range(len(predicates)):
        if not _augment(index, items, predicates, owner, [False] * len(items)):
            return index
    return None


def _augment(
    predicate: int,
    items: "Collection[Any]",
    predicates: "Sequence[Callable[[Any], bool]]",
    owner: "list[int | None]",
    visited: "list[bool]",
    /,
) -> bool:
    """Find an item for ``predicate``, displacing owners that have somewhere to go."""
    test = predicates[predicate]
    for index, item in enumerate(items):
        if visited[index] or not test(item):
            continue
        visited[index] = True
        holder = owner[index]
        if holder is None or _augment(holder, items, predicates, owner, visited):
            owner[index] = predicate
            return True
    return False
