"""How a matcher decides two things are the same, and what it looks inside.

Identity before equality, always. A value whose ``__eq__`` raises, or returns
something that is not a bool, must not turn a matcher into an error -- and a
value compared against itself is equal whatever its ``__eq__`` thinks.

What counts as scannable is narrower than what counts as iterable, on purpose. A
generator is iterable and consuming it to answer a comparison would leave the
caller holding an exhausted object they still expected to be able to read.
"""

from collections.abc import Collection, Mapping
from typing import Any, Final, TypeIs

from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


_MAPPING_OR_TEXT: Final = (Mapping, str, bytes, bytearray)


# ---------------------------------------------------------------------------
# Shared machinery
# ---------------------------------------------------------------------------
def is_mapping(value: object, /) -> "TypeIs[Mapping[Any, Any]]":
    """Whether a value is a mapping, in a shape a type checker can carry forward.

    A bare ``isinstance`` narrows to ``Mapping[Unknown, Unknown]`` under pyright's
    strict mode, and every key read out of it is then an unknown handed to
    something expecting a value. A ``TypeIs`` costs the same one call the ``cast``
    that would otherwise be needed costs, and says what it is doing.
    ``_equivalence.is_mapping`` is the same helper for the same reason.
    """
    return isinstance(value, Mapping)


def is_scannable(value: object, /) -> "TypeIs[Collection[Any]]":
    """Whether a value is a collection ``containing()`` will look through.

    A **mapping** is excluded because iterating one yields its keys, so
    ``containing([1])`` against a dictionary would silently become a claim about
    that dictionary's keys -- a wrong pass, and the kind that reads as correct.
    **Text** is excluded for the reason :data:`_TEXTUAL` gives. Anything left with
    a length, an iterator and a membership test is scanned.
    """
    if isinstance(value, _MAPPING_OR_TEXT):
        return False
    return isinstance(value, Collection)


def equal(expected: object, actual: object, /) -> bool:
    """Python's own containment rule: identity first, then equality.

    Identity first is what lets a NaN be found where it actually sits, and it is
    the rule ``list.__contains__`` and ``_diff.equal`` already follow, so a
    matcher's idea of "holds this" is the language's.

    The *expected* side is compared on the left, which is the one place this
    module departs from what ``x in seq`` does. It has to: the expectation is the
    side a matcher is allowed to be on, and a value class that answers ``False``
    rather than ``NotImplemented`` to an unfamiliar operand -- an ordinary thing
    to write, and no error -- would otherwise shut a nested matcher out of the
    comparison entirely.
    """
    return expected is actual or bool(expected == actual)


def found_in(wanted: object, container: "Collection[object]", /) -> bool:
    """Whether anything in ``container`` equals ``wanted``.

    A scan rather than ``wanted in container``, because ``in`` is a hash lookup
    on a ``set`` or a mapping and a nested matcher cannot be hashed into
    agreement with what it matches (see the module docstring). Quadratic in the
    two sizes, which is the price of the guarantee; the alternative is a matcher
    that works in a list and silently does not in a set.
    """
    for item in container:  # noqa: SIM110  (a generator expression would allocate)
        if equal(wanted, item):
            return True
    return False
