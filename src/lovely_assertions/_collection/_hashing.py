"""One decision: whether a hash table answers the question faster.

A set relation over two containers can be answered by scanning, which is quadratic
and always correct, or through a hash table, which is linear and correct only if
the items hash. The choice is made per call from the sizes involved, because
building a table costs something and a small container never earns it back.

The bounds are all measured against the same question -- would this run have
finished sooner the other way -- and none is offered to the caller. A caller who
could raise one could make a failing assertion slower than the test it is in.
"""

from typing import TYPE_CHECKING

from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Collection

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Container kinds whose ``__contains__`` is a scan, *exactly* -- a subclass may
#: override it, and then a scan is not what it does. ``set``, ``frozenset``,
#: ``range`` and ``dict.keys()`` are absent for the opposite reason: they already
#: answer in constant time, so hashing them a second time would be pure loss.
#:
#: ``dict.values()`` is here and is the surprising member. Its two sibling views
#: are not: ``keys`` is the dictionary's own lookup, and ``items`` is that lookup
#: followed by one comparison. ``values`` has no index at all and walks, so a
#: membership test against a large dictionary's values costs orders of magnitude
#: more than the same test against its keys. It is also the view a mapping subject
#: reaches for, so it is a real collection subject and not a curiosity. Named
#: through ``type(...)`` rather than by importing it, because ``dict_values`` is
#: exported from nowhere and reaching ``types`` for it would be a module-level
#: import bought for one frozenset literal. The empty mapping is annotated only so
#: that a strict checker gets a type parameter for it: ``type({}.values())`` on a
#: bare literal is partially unknown.
_NO_ENTRIES: "dict[object, object]" = {}


_SCANNED_LINEARLY: "frozenset[type[object]]" = frozenset({list, tuple, type(_NO_ENTRIES.values())})


#: Types whose ``__hash__`` and ``__eq__`` are known to agree. *Exactly* these
#: types and not their subclasses, because a subclass may override either one and
#: then nothing is known about the pair again.
#:
#: Small on purpose. Every builtin here is one whose equality is settled by value
#: and whose hash is derived from that same value, the numeric tower included --
#: ``1 == 1.0 == True`` and all three hash to 1, ``0.0 == -0.0`` and both hash to
#: 0. ``datetime``, ``Decimal``, ``UUID`` and ``Enum`` would all qualify and none
#: of them is here: naming them means importing them, and importing this package
#: must not drag in a module that a question about a list of strings has no use
#: for. Their collections take the scan instead.
_HASH_SAFE: "frozenset[type[object]]" = frozenset(
    {bool, bytes, complex, float, int, str, type(None)}
)


#: The three things that must all be true before a hash table is worth building.
#:
#: The container must be long enough to cover the fixed cost of building at all
#: (:data:`_HASHING_PAYS_FROM`), and enough lookups must be coming to amortise it
#: (:data:`_REPEATED_LOOKUPS_FROM`) -- ``contains_any("x")`` against a
#: hundred-thousand-item list is a *single* lookup, and hashing the whole list to
#: answer it is slower than the scan it replaces.
#:
#: The third is the one that is genuinely easy to get wrong. Building costs a hash
#: plus a type check per item of the container, both of which have to walk it, so
#: the decision is ``O(n)`` **whatever it decides**. A scan does *not* cost
#: ``O(n)`` per lookup. It costs one comparison per item it passes before it finds
#: what it is looking for, and stops. So the scan's price turns on where the
#: needles *are*, not merely on how many there are, and the worst case is the only
#: case in which "both sides are linear in n and it cancels" is true.
#:
#: The shape that makes the point: a handful of needles that all sit at the front
#: of a very long list. The scan answers in microseconds and hashing the list takes
#: milliseconds -- orders of magnitude slower, to answer the same question, on a
#: shape nobody would call exotic, since an early slice of a sorted collection is
#: exactly that. Unbounded, too: the ratio grows with the container.
#:
#: No floor on the lookup count alone can bound that, because the best case a scan
#: can have costs ``O(m)`` however large ``m`` is. What bounds it is requiring the
#: container to be no more than :data:`_LONGEST_CONTAINER_PER_LOOKUP` times the
#: lookup count, which caps the loss at roughly that ratio's worth against a best
#: case that was already microseconds, while keeping every win the table was built
#: for. Those wins are all shaped ``m ~ n`` -- two long lists compared item for
#: item, a mapping's values against another mapping's keys -- and they sail
#: through, turning tens of seconds into milliseconds.
#:
#: What the gate still costs where it opens too eagerly, stated rather than
#: hidden: at exactly the two floors, with hashable integers on both sides, the
#: scan is marginally faster than the table built to replace it -- a single-digit
#: percentage, paid on the smallest collection the gate ever opens for.
_HASHING_PAYS_FROM = 32


_REPEATED_LOOKUPS_FROM = 16


_LONGEST_CONTAINER_PER_LOOKUP = 8


def searchable(
    items: "Collection[object]", container: "Collection[object]", /
) -> "Collection[object]":
    """``container``, or a set that answers ``in`` for it *identically* and faster.

    ``item in some_list`` is a scan, so asking it once per item turns every
    set-like relation in this module into ``O(n * m)`` -- two long lists compared
    against each other take tens of seconds. Hashing the container once and asking
    the hash table instead brings the same comparison down to milliseconds.

    It is also, in general, **a different question**, which is why this returns
    the container unchanged far more often than it returns a set.

    *What a set does not change.* Identity survives it. ``in`` compares
    ``x is y or x == y`` item by item, and a set does the same inside the bucket
    it lands in -- CPython compares the stored pointer before it compares the
    objects. So the NaN case that this module spells out at eight sites is safe:
    a collection holding a NaN contains *that* NaN either way, because the lookup
    hashes the very object that is stored and lands in its bucket. Two distinct
    NaNs are absent from each other either way, for the matching reason -- a float
    NaN hashes by identity, so they do not even share a bucket.

    *What a set does change*, and it is not academic:

    * **A type whose hash disagrees with its equality.** Value equality with an
      identity hash is the standard ORM row: ``a == b`` is true and
      ``hash(a) != hash(b)``, so ``b in [a]`` finds it and ``b in {a}`` does not.
      Python documents that pair as an invariant, and the types that break it
      break it deliberately.
    * **A needle the container's own type would never have matched.** Membership
      compares ``element == needle`` with the reflected fallback, so an object
      with a permissive ``__eq__`` is found in a list of strings and is not found
      in a set of them.
    * **An unhashable needle.** ``["x"] in ["a"]`` is ``False``; ``["x"] in {"a"}``
      is a ``TypeError``.

    So the gate is on **types, on both sides**, rather than on a ``try`` around
    the build. Catching ``TypeError`` would cover only the third of those three --
    the two that return a *wrong answer* instead of raising are exactly the two it
    cannot see, and they are the ones that matter.

    That check walks the container, so it is ``O(n)`` and it is spent *before* the
    answer is known -- twice the cost of the ``set`` it is deciding about, and paid
    in full on a container that turns out to hold a ``Decimal`` in its last slot.
    That is the reason the length gate is not the only gate: see
    :data:`_LONGEST_CONTAINER_PER_LOOKUP`, which is what keeps an ``O(n)`` decision
    from being taken on behalf of a handful of lookups that a scan would have
    answered in microseconds.

    The cost of that strictness is stated rather than hidden: a collection of
    dataclasses, ``Decimal`` or ``datetime`` keeps the quadratic scan even though
    its hashing is perfectly well behaved. That is the trade this module makes
    everywhere -- a right answer slowly beats a wrong one quickly -- and the way
    out is to widen :data:`_HASH_SAFE` with a type whose contract can be *read*,
    never to guess from behaviour.

    Returns the container itself rather than ``None`` for "scan it", so that every
    caller is one loop over one name and the two paths cannot drift into two
    answers. What that shape costs the small case is a call, two ``len`` and two
    comparisons -- a measurable fraction of a three-item relation, and the guards
    are ordered cheapest first so that a small collection is only ever charged
    those. Writing the gate out at each call site instead buys back about half of
    that and puts the decision about what ``in`` means in several places rather
    than one.
    """
    held = len(container)
    lookups = len(items)
    if held < _HASHING_PAYS_FROM or lookups < _REPEATED_LOOKUPS_FROM:
        return container
    if lookups * _LONGEST_CONTAINER_PER_LOOKUP < held:
        return container
    if type(container) not in _SCANNED_LINEARLY:
        return container
    for item in container:
        if type(item) not in _HASH_SAFE:
            return container
    for item in items:
        if type(item) not in _HASH_SAFE:
            return container
    return set(container)
