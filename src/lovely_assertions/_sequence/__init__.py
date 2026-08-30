"""Assertions for sequences -- the half of the collection catalogue that order makes meaningful.

The richest catalogue in the library, and the one where the message engine earns
its keep. A collection assertion that only reports *false* leaves the reader to
diff two lists by eye, so every failure here names what was expected, what was
actually there, and -- wherever there is one -- the exact position of the
disagreement.

What lives here is what **order** makes meaningful: ordered equality, prefixes and
suffixes, indexing, "in this order", sortedness. Everything a collection can
answer without an order -- length, membership, set relations, per-item
inspections -- lives one class up in
:class:`~lovely_assertions._collection.CollectionExpect` and is inherited whole.
The two positional message hooks are overridden here, which is what keeps the
inherited half saying ``at index 3`` when the subject really has an index 3.

Four conventions run through the module.

**An assertion that cannot tell must not answer "no problem".** Both halves of
the catalogue compare, and both have a value that makes a comparison answer
false without meaning it: a NaN, which is equal to nothing and ordered against
nothing, and a type with a hostile ``__eq__``. Left alone, that silence reads as
agreement and the assertion passes vacuously -- the tell being an assertion and
its negation *both* passing on one subject. So equality here is Python's own
membership rule, ``x is y or x == y``, spelled inline at every comparison site
(the rule :func:`~lovely_assertions._collection._count_equal` states, so that
``contains`` and ``contains_in_order`` cannot disagree about what a list holds),
and sortedness asks whether a pair is definitely *in* order -- strictly ordered
or equal -- rather than definitely out of it, so an unordered neighbour is
reported at the index where it breaks the order instead of being waved through
by both ``is_sorted`` and ``is_sorted_descending``. The inclusive question is
built from ``<`` and ``==`` rather than ``<=``, so that an element or a ``key=``
result still needs no operator beyond the one ``sorted()`` needs. The one
deliberate exception is :meth:`SequenceExpect.equals_approximately`, where a NaN
is close to nothing -- itself included -- because that is the contract
``is_close_to`` states and it is a claim about distance, not about which items a
sequence holds.

**Collections in messages go through :func:`~lovely_assertions._collection.render_items`**,
which truncates long ones. A message that pastes ten thousand elements hides the
finding instead of explaining it.

**Comparisons are element-wise**, never ``==`` between the collections
themselves: the subject type is ``Sequence``, so a ``list`` is compared against
the ``tuple`` with the same contents on its merits.

**Element-valued parameters are typed ``E``**, not ``object``. ``expect(names)``
should refuse ``contains(3)`` when ``names`` is a ``Sequence[str]`` -- an
assertion that can only ever fail is a bug in the test, and catching it before
the suite runs is the point of the typed surface.

The catalogue is assembled from one mixin per seam over a shared root that
carries the two position hooks. Everything an unordered collection can also
answer arrives through that root, from ``CollectionExpect``.
"""

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._sequence._access import AccessAssertions
from lovely_assertions._sequence._base import SequenceBase
from lovely_assertions._sequence._containment import ContainmentAssertions
from lovely_assertions._sequence._equality import EqualityAssertions
from lovely_assertions._sequence._nested import NestedAssertions
from lovely_assertions._sequence._ordering import OrderingAssertions
from lovely_assertions._sequence._projection import ProjectionAssertions

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["SequenceExpect"]


class SequenceExpect[E](
    EqualityAssertions[E],
    AccessAssertions[E],
    ContainmentAssertions[E],
    OrderingAssertions[E],
    ProjectionAssertions[E],
    NestedAssertions[E],
    SequenceBase[E],
):
    """Assertions for sequences, parameterised by element type.

    The subject is a ``Sequence``, not a ``list``: indexing, ``len`` and repeated
    iteration are fair game, mutation is not, and one subject class covers lists,
    tuples and anything else that behaves like a sequence.

    Everything an unordered collection can also answer is inherited from
    :class:`~lovely_assertions._collection.CollectionExpect`; what is declared
    here is what an order makes meaningful.
    """

    __slots__ = ()
