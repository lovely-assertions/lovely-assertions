"""What a value is, and what can be read off it.

Before two values can be compared member by member, something has to decide what
their members *are*: a mapping whose keys are its data, a record whose author
declared its fields, a sequence, a set, or a leaf with nothing inside worth taking
apart. That is this package. It is the only part of the engine that asks its
questions of a value's *class* rather than of its contents, which is why it is
also where the engine keeps its caches, and why it sits apart from the walk that
consumes what it decides.

Three concerns, one per module, and they stack.
:mod:`lovely_assertions._equivalence._classification._fields` reads names -- the
ones a dataclass, a NamedTuple or an attrs class declares, and the ones an
instance turns out to be storing in ``__slots__`` and its dictionary.
:mod:`lovely_assertions._equivalence._classification._opacity` answers the
question asked before any of that: whether there is anything inside this value at
all. :mod:`lovely_assertions._equivalence._classification._routing` puts the
branches in order and hands back a kind, together with the fields to compare when
that kind is a record.

The order those branches are tried in is the load-bearing part, and ``_routing``
carries the argument for each position. Getting one wrong does not produce a worse
report: it produces a comparison that takes two values apart on the wrong members,
finds that those members agree, and reports the pair equivalent.

Nothing here imports ``dataclasses``, ``attrs`` or ``enum``. A declaration is
found by the mark its machinery leaves on the class and read through
:mod:`lovely_assertions._reflection`, and an enumeration member is duck-typed on
what the ``enum`` runtime leaves on the class and on the member -- because a
comparison that never meets one should not pay for the import.
"""

from lovely_assertions._equivalence._classification._fields import UNRESOLVED as UNRESOLVED
from lovely_assertions._equivalence._classification._fields import (
    declared_field_names as declared_field_names,
)
from lovely_assertions._equivalence._classification._fields import is_enum_member as is_enum_member
from lovely_assertions._equivalence._classification._fields import (
    stored_field_names as stored_field_names,
)
from lovely_assertions._equivalence._classification._opacity import is_opaque as is_opaque
from lovely_assertions._equivalence._classification._routing import KIND_LEAF as KIND_LEAF
from lovely_assertions._equivalence._classification._routing import KIND_MAPPING as KIND_MAPPING
from lovely_assertions._equivalence._classification._routing import KIND_SEQUENCE as KIND_SEQUENCE
from lovely_assertions._equivalence._classification._routing import KIND_SET as KIND_SET
from lovely_assertions._equivalence._classification._routing import ROUTE_BY_TYPE as ROUTE_BY_TYPE
from lovely_assertions._equivalence._classification._routing import ROUTE_TOKEN as ROUTE_TOKEN
from lovely_assertions._equivalence._classification._routing import classify as classify
from lovely_assertions._exceptions import hide_internal_frames

__all__ = [
    "KIND_LEAF",
    "KIND_MAPPING",
    "KIND_SEQUENCE",
    "KIND_SET",
    "ROUTE_BY_TYPE",
    "ROUTE_TOKEN",
    "UNRESOLVED",
    "classify",
    "declared_field_names",
    "is_enum_member",
    "is_opaque",
    "stored_field_names",
]

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames
