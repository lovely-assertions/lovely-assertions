"""The entry point, and the table that routes a pair to its describer.

The branch order is the file's content: a mapping is a collection, a NamedTuple
is a sequence, and a string is a sequence of strings each of which is a sequence
of strings. Every one of those has to be claimed by the describer that says the
most about it, before a more general one gets the chance -- which is why this
reads as a list of tests in a fixed order rather than as a lookup.

The blanket ``except`` is the contract. This code runs inside a failing
assertion, describing values that are already suspect; a describer that raises
would replace a readable failure with a traceback into the library. Every path
out of here returns text, including the path where the value fought back.
"""

from lovely_assertions._diff._mappings import describe_mapping
from lovely_assertions._diff._objects import describe_object
from lovely_assertions._diff._primitives import is_plain_sequence
from lovely_assertions._diff._render import describe_look_alike
from lovely_assertions._diff._sequences import describe_sequence_or_record
from lovely_assertions._diff._sets import describe_set
from lovely_assertions._diff._strings import describe_text
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._reflection import is_mapping, is_set

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def describe_difference(actual: object, expected: object, /) -> str:
    """A rendered account of how two unequal values differ.

    Returns "" when a plain repr of both already tells the whole story, so the
    caller can append the result unconditionally. Otherwise returns a block that
    starts with a newline and does not end with one.

    The blanket ``except`` is the contract, not laziness: this runs on the failure
    path of an assertion that has *already* failed, and a hostile ``repr``, a
    ``__eq__`` that raises, or a self-referential structure must cost the reader a
    less detailed message -- never turn their test failure into a library error.
    """
    try:
        lines = _describe(actual, expected, 0)
    except Exception:
        return ""
    if not lines:
        return ""
    return "\n" + "\n".join(lines)


def _describe(actual: object, expected: object, depth: int, /) -> list[str]:
    """The lines describing one pair, without the leading newline."""
    lines = describe_by_kind(actual, expected, depth)
    if lines:
        return lines
    return describe_look_alike(actual, expected, depth)


def describe_by_kind(actual: object, expected: object, depth: int, /) -> list[str]:
    """Route a pair to the describer for its kind; ``[]`` when the kinds disagree.

    Two values of different kinds have nothing structural in common, so there is
    nothing to say that their reprs do not already show. ``str`` is tested first
    because a string is also a ``Sequence``, and ``bytes`` is excluded for the
    same reason it is excluded from ``SequenceExpect``: iterating it yields
    integers, which is never what the reader meant.

    The position of the last branch is the load-bearing part. Every object is
    asked about *after* the sequence branch, so that a list subclass which happens
    to carry an attribute is still diffed as the list its ``__eq__`` compares it
    as. A NamedTuple is a tuple and so lands in the sequence branch too, which
    reads its names from inside -- see :func:`describe_sequence_or_record`.
    """
    if isinstance(actual, str) and isinstance(expected, str):
        return describe_text(actual, expected, depth)
    if is_mapping(actual) and is_mapping(expected):
        return describe_mapping(actual, expected, depth)
    if is_set(actual) and is_set(expected):
        return describe_set(actual, expected, depth)
    if is_plain_sequence(actual) and is_plain_sequence(expected):
        return describe_sequence_or_record(actual, expected, depth)
    return describe_object(actual, expected, depth)
