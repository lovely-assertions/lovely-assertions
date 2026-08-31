"""What sortedness compares, and how it decides.

The key protocol is the caller's escape hatch: a sequence of records is rarely
ordered by the records themselves. Without a key the items are compared directly,
which is what a reader means by "sorted" nine times in ten.

The scan returns the first pair that is out of order rather than a verdict, so
the message can name the two items and where they are -- ``sorted() == subject``
would answer the same question and have nothing to say about it.
"""

from typing import TYPE_CHECKING, Any, Protocol, cast

from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class Sortable(Protocol):
    """What a sort key may return -- the requirement the ordering assertions have.

    Named for the question rather than for the operator, because
    :class:`~lovely_assertions._ordered.Ordered` states the same requirement for a
    different subject and a reader meeting both in one catalogue would have to
    work out which one a signature meant.

    ``_typeshed.SupportsRichComparison`` is the obvious candidate and does not
    work: it is a *union* of the two half-protocols, and neither checker will
    compare one member of that union against the other.

    ``<`` alone, and it stays that way: unlike
    :class:`lovely_assertions._ordered.Ordered`, which names all four operators
    because ``is_greater_than_or_equal_to`` is literally spelled ``>=``, nothing
    here needs more than the one operator ``sorted()`` itself needs.
    :func:`first_out_of_order` asks its inclusive question out of ``<`` and
    ``==`` for exactly that reason. This protocol is part of the published
    surface -- it is what every ``key=`` parameter in the ordering assertions
    promises -- so widening it would start raising ``TypeError`` on a user type
    that defines only ``__lt__``, which is perfectly sortable.
    """

    __slots__ = ()

    def __lt__(self, other: Any, /) -> bool:  # noqa: ANN401  (the operand is the caller's business)
        ...


def sort_key(item: object, key: "Callable[[Any], Sortable] | None", /) -> Sortable:
    """The value ordering compares: the item itself, or what ``key`` makes of it."""
    if key is None:
        return cast("Sortable", item)
    return key(item)


def first_out_of_order(
    items: "Sequence[object]", key: "Callable[[Any], Sortable] | None", /, *, descending: bool
) -> int | None:
    """Index of the first item that breaks the ordering, or ``None``.

    Equal neighbours are in order either way, so this reports strict violations
    only -- ``[1, 1, 2]`` is both sorted and not sorted descending.

    The question asked is "is this pair definitely *in* order?" -- strictly
    ordered, or equal -- and the loop returns on its negation. Asking the
    opposite, "is this pair definitely *out* of order?", is the whole difference
    between reporting a NaN and being silenced by one: every comparison involving
    a NaN is false, so the strict spelling gets ``False`` from a pair it cannot
    order at all and waves it through. That reading would let ``[3.0, nan, 1.0]``
    satisfy ``is_sorted`` *and* ``is_sorted_descending``, two assertions that are
    supposed to be opposites. Asked the answerable question, a pair that cannot
    answer is reported at the index where it breaks the order.

    The inclusive question is built out of ``<`` and ``==`` rather than spelled
    ``<=``, and that is deliberate rather than long-winded. ``<`` is the only
    ordering operator this module requires of an element or of a ``key=``
    result: it is what :class:`Sortable` promises, what every ``key=`` signature
    in the module publishes, and all ``sorted()`` itself asks for. ``previous <=
    current`` would demand ``__le__`` and ``__ge__`` too, and a type defining
    only ``__lt__`` -- perfectly sortable, and the exact shape the protocol
    describes -- would then raise ``TypeError`` from every ordering assertion.

    The ``==`` is nearly free: it is reached only once the strict test has
    already said no, which on an ordered subject means at ties alone. The whole
    condition is written inline rather than through a local because that was
    measured, not assumed -- binding the pair to locals costs a few percent on an
    ordinary subject, while the inline form is at parity with the bare strict
    test, and only an all-ties subject, the one shape where ``==`` really is
    evaluated at every step, pays anything at all.

    Identity is deliberately *not* consulted here, unlike at the equality sites.
    Two references to one NaN are still an unordered pair: ``is`` answers a
    question about which item this is, not about how two of them compare.

    A ``Decimal`` NaN is not covered by this and is not meant to be: its
    orderings *signal* rather than return false, so the ``InvalidOperation`` it
    raises propagates instead of being turned into a verdict -- the scalar
    ordering subject in :mod:`lovely_assertions._ordered` makes the same choice,
    and for the same reason: a signal is the caller's configuration talking, not
    a finding about the sequence.
    """
    count = len(items)
    if count == 0:
        return None
    previous = sort_key(items[0], key)
    for index in range(1, count):
        current = sort_key(items[index], key)
        if not (current < previous if descending else previous < current) and previous != current:
            return index
        previous = current
    return None
