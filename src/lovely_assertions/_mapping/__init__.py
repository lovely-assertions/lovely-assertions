"""Assertions for mappings.

What a failed mapping assertion mostly has to say is *what was actually in
there*, so the messages here are built on two shared pieces: a capped preview of
the keys (or values) that were present, and -- when a lookup misses a key by what
looks like a typo -- a ``difflib`` suggestion naming the key that was probably
meant. Both run on the failure path only, and ``difflib`` is imported inside the
branch that needs it: importing this package must not drag in a module that only
a failing assertion has any use for. The cap is
``current_formatting().max_items``, read where the preview is built, so a
:func:`~lovely_assertions._formatting.formatting` block can widen the one failure
whose interesting key is the fiftieth.

**Containment is tested with ``x is y or x == y``**, Python's own rule -- what
``value in mapping.values()`` does, and what ``dict.__eq__`` does value by value.
Equality alone would report a value the mapping demonstrably holds as absent
whenever that value is not equal to itself (``float("nan")`` is the one everybody
meets), which would make ``contains_value`` contradict ``contains_values`` and
``contains_entry`` contradict the inherited ``is_equal_to``. The rule is written
out at each site rather than put in a helper: these are the comparisons the happy
path pays for, and a call per candidate is a cost a passing assertion should not
be charged.

**The keys and the values are subjects of their own.** ``.keys`` and ``.values``
hand back a :class:`~lovely_assertions._collection.CollectionExpect` over the
live view, so the whole order-free catalogue -- uniqueness, subset and superset,
element types, nested inspection -- applies to them without a second
implementation here. ``expect()`` already dispatches ``dict.keys()`` to that
subject; the properties only save the round trip.

The catalogue is assembled from one mixin per seam. Each is an
``Expect[Mapping[K, V]]`` with empty ``__slots__``, so a mapping subject is still
one allocation carrying one attribute.
"""

from collections.abc import Mapping

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._mapping._entries import EntryAssertions
from lovely_assertions._mapping._keys import KeyAssertions
from lovely_assertions._mapping._size import SizeAssertions
from lovely_assertions._mapping._values import ValueAssertions
from lovely_assertions._mapping._views import ViewAssertions

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["MappingExpect"]


class MappingExpect[K, V](
    SizeAssertions[K, V],
    ViewAssertions[K, V],
    KeyAssertions[K, V],
    ValueAssertions[K, V],
    EntryAssertions[K, V],
    Expect[Mapping[K, V]],
):
    """Assertions for mappings, parameterised by key and value type."""

    __slots__ = ()
