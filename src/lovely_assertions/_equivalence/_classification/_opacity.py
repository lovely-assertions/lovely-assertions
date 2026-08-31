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


def is_opaque(value: object, /) -> bool:
    """Whether a value has no structure this engine will look inside.

    Three kinds, and each goes wrong in its own way if it falls through.

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
    """
    return isinstance(value, _OPAQUE_TYPES) or is_enum_member(value)
