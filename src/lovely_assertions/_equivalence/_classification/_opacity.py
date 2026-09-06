"""The values this engine will not look inside.

Opacity is the first question the routing order asks: before a kind is chosen or
a field is read, whether there is anything in here worth taking apart at all.
That is what puts this module between the other two -- above the reader it borrows
:func:`is_enum_member` from, below the routing that asks it first.

Being wrong here is never merely a worse report. Walked instead of compared
whole, a string descends into strings that iterate to themselves, a class is
compared on the methods it defines rather than on any state, and an enumeration
member is compared on attributes two members with different values can agree on
-- which is a pair that differs reported equivalent. The case for each is on the
function itself.
"""

from typing import Final

from lovely_assertions._equivalence._classification._fields import is_enum_member
from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Types whose values are compared whole, built once instead of at every call.
#: ``isinstance(value, str | bytes | ...)`` reads as the nicer spelling and is
#: not: the ``|`` builds a fresh ``UnionType`` every time it is evaluated, where a
#: tuple bound at import costs nothing per call and is what ``isinstance`` wants
#: anyway.
_OPAQUE_TYPES: Final = (str, bytes, bytearray, memoryview, type)


#: The class attribute a matcher carries, looked for by name.
#:
#: A string and not an import, deliberately. Nothing in this engine knows the
#: matchers exist -- that is what lets a matcher work without a single assertion
#: being written for it -- and an import here would spend that for one predicate.
#: Asked of the class rather than the instance, the shape ``_mock._recognition``
#: uses for the same reason: a miss allocates nothing, and the answer cannot
#: differ between two instances of one class.
#:
#: The matcher package owns the spelling and names it there; this is the reading
#: end. The two are one string written twice, so changing either without the
#: other silently stops every matcher being recognised here -- the messages go
#: back to naming a private class, and nothing else breaks. A test pins the pair
#: against each other for exactly that reason.
_MATCHER_MARKER: Final = "_stands_for_a_value_"


def stands_for_a_value(value: object, /) -> bool:
    """Whether ``value`` is a placeholder standing in for a value it is not.

    A matcher, in other words -- but asked without naming the package that
    defines one. **Failure path only** in every caller it has today, and cheap
    either way: a miss is one failed attribute lookup on a class.
    """
    return getattr(type(value), _MATCHER_MARKER, False) is True


def is_opaque(value: object, /) -> bool:
    """Whether a value has no structure this engine will look inside.

    Four kinds, and each goes wrong in its own way if it falls through.

    ``str`` and the buffers beside it are sequences and none of them is ever
    walked as one: iterating a string yields strings that iterate to themselves,
    and iterating ``bytes``, ``bytearray`` or a ``memoryview`` yields integers
    nobody indexed by hand.

    A class object's own dictionary holds the methods it defines, not the state an
    instance carries. A class is not a record.

    An **enumeration member** *is* its value; there is no state underneath to take
    apart. Left to the record branch, a member of an enum whose ``__init__``
    assigns attributes is compared on those attributes alone -- and two members
    that agree on them, under different values, come back **equivalent**.
    Dropping the names the runtime reserves for itself -- ``_name_``, ``_value_``
    and the rest of that spelling, which the field readers already discard -- does
    not cover it: that empties a plain member down to a leaf and leaves a mixed-in
    one a record.

    A **matcher** has no state to compare either: it stands in for a value rather
    than being one, and its fields are the specification it was built from, which
    is exactly what its own ``==`` exists to interpret. Taking one apart would
    report a private class name in place of the phrase it renders as. It reaches
    this branch as a leaf today whatever this function says, because every matcher
    spells its slots so the field readers discard them -- so naming it here buys
    the guarantee rather than the behaviour, and stops that spelling from being
    the only thing holding the message together.
    """
    return isinstance(value, _OPAQUE_TYPES) or is_enum_member(value) or stands_for_a_value(value)
