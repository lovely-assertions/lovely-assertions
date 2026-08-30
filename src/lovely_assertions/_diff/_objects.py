"""Two records compared field by field, once that is worth doing at all.

The early return is the part worth reading. A class that never defined ``__eq__``
is compared by identity, so two instances holding identical fields are unequal
and a field-by-field report would list nothing and explain nothing -- the
difference is that they are different objects, and saying so is the whole answer.

Across two types the types are themselves the finding, so only the fields both
sides carry are worth comparing and a field only one side declares is left out
entirely -- a subclass declaring a field its base does not is what subclassing
is, rather than a difference between two values.
"""

from lovely_assertions._diff._fields import differing_field_lines, field_lines, field_names
from lovely_assertions._diff._primitives import indentation
from lovely_assertions._diff._type_notes import different_types_note, is_related
from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def describe_object(actual: object, expected: object, depth: int, /) -> list[str]:
    """Field by field, for the composite type Python actually has most of.

    Reached for anything the container describers did not claim: a dataclass, a
    ``__slots__`` class, a plain object with a ``__dict__``, and -- with nothing
    imported to recognise them -- an attrs class or a pydantic model. This is the
    one place pytest's rewriting still wins on the common case, because
    ``User(name='ann', age=30)`` against ``User(name='ann', age=31)`` is two
    reprs the reader has to diff by eye. (A NamedTuple is a record too, but it
    reaches its field names through the sequence branch, which is where being a
    tuple lands it; it arrives here only when the other side is not a sequence
    at all.)

    Silent for anything that resolves no fields at all, which is how ``3``, a
    function and a bare ``object()`` fall straight through to the look-alike
    clause below.
    """
    actual_fields = field_names(actual)
    expected_fields = field_names(expected)
    if not actual_fields or not expected_fields:
        return []
    actual_type = type(actual)
    expected_type = type(expected)
    if actual_type is not expected_type:
        return cross_type_lines(actual, expected, actual_fields, expected_fields, depth)
    if actual_type.__eq__ is object.__eq__:
        # The fields are not why this failed and never could be: the type compares
        # by identity, so two instances are unequal however their fields read.
        # Returning nothing hands the pair to `describe_look_alike`, which says
        # the thing that is actually wrong -- the type has no `__eq__`.
        return []
    return field_lines(actual, expected, actual_fields, expected_fields, depth)


def cross_type_lines(
    actual: object,
    expected: object,
    actual_fields: tuple[str, ...],
    expected_fields: tuple[str, ...],
    depth: int,
    /,
) -> list[str]:
    """Name both types, and add the fields only when the types leave room for them.

    Two *unrelated* types are the whole finding. Every generated ``__eq__`` in
    the ecosystem -- ``dataclass``, ``NamedTuple``, attrs, pydantic -- refuses a
    different class outright, so no arrangement of the fields would have made
    these two equal, and a field-by-field diff between them would bury the one
    finding there is under differences that are beside the point.

    When one type *derives* from the other the note is still worth its line and
    is no longer the whole answer: the ``__eq__`` they share is very often the
    hand-written ``isinstance`` kind, which compares a ``Cash`` to a ``Money``
    happily. Left alone, "types differ" would send the reader hunting for a
    construction bug when the amount is what is wrong. The membership half stays
    out -- a subclass declaring a field its base does not is what subclassing
    *is*, not a finding.
    """
    actual_type = type(actual)
    expected_type = type(expected)
    lines = [indentation(depth) + different_types_note(actual_type, expected_type)]
    if not is_related(actual_type, expected_type):
        return lines
    on_actual = frozenset(actual_fields)
    shared = [name for name in expected_fields if name in on_actual]
    lines.extend(differing_field_lines(actual, expected, shared, depth))
    return lines
