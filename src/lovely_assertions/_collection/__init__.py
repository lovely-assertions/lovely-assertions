"""Assertions for collections with no order of their own.

``Collection`` gives three things and nothing else: ``__len__``, ``__iter__`` and
``__contains__``. Everything in this module is written to that budget, which is
what lets one subject cover ``set``, ``frozenset``, ``dict.keys()``,
``dict.items()``, ``dict.values()`` and any user collection alongside the lists
and tuples that :class:`~lovely_assertions._sequence.SequenceExpect` refines.

The split is a promise about *meaning*, not a convenience. ``is_sorted`` on a set
is not a slow assertion or an awkward one -- it is a question with no answer, and
the point of a typed assertion library is that such a question is rejected by a
type checker rather than answered at random. So the order-dependent catalogue
lives one class down and is unreachable from here.

Three conventions run through the module.

**Collections in messages go through :func:`render_items`**, which truncates long
ones. A message that pastes ten thousand elements hides the finding instead of
explaining it. How much it prints is the caller's to change -- ``max_items`` in a
:func:`~lovely_assertions._formatting.formatting` block -- because the truncation
that keeps a message readable is exactly what hides the four-hundredth row when
the four-hundredth row is the one being looked for.

**Positions are asked for, never assumed.** A failure inside an unordered
collection has no index to report, so the positional half of a message comes from
:meth:`CollectionExpect._position`, which is empty here and says ``at index N``
in the sequence subject. One implementation, two truthful messages.

**Element-valued parameters are typed ``E``**, not ``object``. ``expect(names)``
should refuse ``contains(3)`` when ``names`` is a ``Collection[str]`` -- an
assertion that can only ever fail is a bug in the test, and catching it before
the suite runs is the point of the typed surface.

The catalogue is assembled from one mixin per seam over a shared root that
carries the four message-position hooks. Each seam is a ``CollectionBase[E, C]``
with empty ``__slots__``, so a collection subject is still one allocation.
"""

from collections.abc import Collection
from typing import Any

from lovely_assertions._collection._base import CollectionBase
from lovely_assertions._collection._containment import ContainmentAssertions
from lovely_assertions._collection._element_types import ElementTypeAssertions
from lovely_assertions._collection._emptiness import EmptinessAssertions
from lovely_assertions._collection._length import LengthAssertions
from lovely_assertions._collection._multi_item import MultiItemAssertions
from lovely_assertions._collection._nested import NestedAssertions
from lovely_assertions._collection._overlap import OverlapAssertions
from lovely_assertions._collection._predicates import PredicateAssertions
from lovely_assertions._collection._projection import ProjectionAssertions
from lovely_assertions._collection._relations import RelationAssertions
from lovely_assertions._collection._render import in_message_order, render_items, render_or_none
from lovely_assertions._collection._screening import ScreeningAssertions
from lovely_assertions._collection._wildcards import WildcardAssertions
from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["CollectionExpect", "in_message_order", "render_items", "render_or_none"]


class CollectionExpect[E, C: Collection[Any] = Collection[E]](
    EmptinessAssertions[E, C],
    LengthAssertions[E, C],
    ContainmentAssertions[E, C],
    PredicateAssertions[E, C],
    ScreeningAssertions[E, C],
    ElementTypeAssertions[E, C],
    RelationAssertions[E, C],
    OverlapAssertions[E, C],
    MultiItemAssertions[E, C],
    NestedAssertions[E, C],
    WildcardAssertions[E, C],
    ProjectionAssertions[E, C],
    CollectionBase[E, C],
):
    """Assertions that do not depend on order, parameterised by element type.

    ``E`` is the element type. ``C`` is the container, and exists so that
    :class:`~lovely_assertions._sequence.SequenceExpect` can inherit this
    catalogue while keeping ``.subject`` typed as the ``Sequence`` it really has.
    It defaults to ``Collection[E]``, so the subject is written ``CollectionExpect[str]``
    everywhere it is named.

    A user's own subject subclasses it the same way::

        class TagsExpect(CollectionExpect[str]):
            __slots__ = ()
    """

    __slots__ = ()
