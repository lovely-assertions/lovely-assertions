"""What to say when the two values are not of the same kind.

A type difference is the one finding that makes every other one beside the point:
once the expected value is a tuple and the actual is a list, a report about which
index disagrees is answering a question nobody asked. So these notes are built by
the describers rather than by the renderer, and each says what it can prove --
that the contents match and only the container differs, or that the two types are
related closely enough for the confusion to be worth naming.
"""

from lovely_assertions._diff._primitives import indentation
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._reflection import qualified

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def type_note(actual: object, expected: object, noun: str, depth: int, /) -> list[str]:
    """The note for two containers holding the same ``noun`` that are still unequal.

    ``[1, 2] == (1, 2)`` is false and the reprs differ by two characters. Saying
    which two saves a reader the minute they would otherwise spend re-reading them.
    """
    actual_type = type(actual)
    expected_type = type(expected)
    if actual_type is expected_type:
        return []
    return [
        indentation(depth)
        + "the same "
        + noun
        + ", but actual is a "
        + actual_type.__name__
        + " and expected is a "
        + expected_type.__name__
    ]


def different_types_note(actual_type: type, expected_type: type, /) -> str:
    """Name both types, in the vocabulary the rest of the block uses."""
    actual_name = actual_type.__name__
    expected_name = expected_type.__name__
    if actual_name == expected_name:
        # Two classes of one name is the case where the two reprs above are of no
        # help whatsoever, so it is the one worth spelling out in full.
        actual_name = qualified(actual_type)
        expected_name = qualified(expected_type)
    if actual_name == expected_name:
        return (
            "types differ: both are called "
            + actual_name
            + ", but they are not the same class object"
        )
    # "actual instead of expected", the order every other line of the block uses.
    # An article would have to go in front of each name, and no rule on a first
    # letter gets both "a Admin" and "an User" right.
    return "types differ: " + actual_name + " instead of " + expected_name


def is_related(actual_type: type, expected_type: type, /) -> bool:
    """Whether one of the two types derives from the other.

    ``issubclass`` runs the metaclass's ``__subclasscheck__``, which is somebody
    else's code and is under no obligation to answer. Unrelated is the safe
    assumption when it will not: the note above stands on its own, where letting
    the exception out would cost the reader the whole block.
    """
    try:
        return issubclass(actual_type, expected_type) or issubclass(expected_type, actual_type)
    except Exception:
        return False
