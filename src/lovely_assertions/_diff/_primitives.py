"""The leaf operations the rest of the engine is built out of.

Nothing here knows what is being compared. Every function is a small, total
answer -- how a value is spelled once the scope's budget is applied, how a block
is indented, whether two values are equal without trusting either one's
``__eq__`` to behave -- and nothing in this file imports another module of the
package's diff engine. That is what makes it the bottom of the graph: every other
module may reach down to it, and a cycle cannot form through it.
"""

from collections.abc import Sequence
from typing import Any, Final, TypeIs, cast

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._formatting import current_formatting

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: One level of the block. The whole thing is indented under a one-line message.
INDENT: Final = "  "


#: Characters of common prefix quoted back to locate a difference inside a long
#: single-line string. Enough to search for, short enough to sit in a clause.
CONTEXT_CHARS: Final = 20


def clip(text: str, /) -> str:
    """Cut an over-long rendering down, saying how much was cut.

    The bound is read here rather than passed in, at every single place a value is
    rendered. That is a ``ContextVar`` lookup per rendered value, which is
    affordable precisely because none of it happens until an assertion has already
    failed -- and it is what lets one ``formatting(...)`` block widen every value
    in a message without threading an options record through every function in the
    module.
    """
    max_chars = current_formatting().max_chars
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "... (" + str(len(text) - max_chars) + " more characters)"


def indentation(depth: int, /) -> str:
    """The block sits under a one-line message, and nests with the structure."""
    return INDENT * (depth + 1)


def common_prefix_length(actual: str, expected: str, /) -> int:
    """How many leading characters the two strings share."""
    limit = min(len(actual), len(expected))
    for index in range(limit):
        if actual[index] != expected[index]:
            return index
    return limit


def equal(actual: object, expected: object, /) -> bool:
    """Python's own containment rule: identity first, then equality.

    Identity first is what makes a ``float("nan")`` compare equal to itself, the
    same rule ``list.__eq__`` and ``dict.__eq__`` apply internally, and the one
    ``_mapping.py`` spells out at each of its comparison sites.
    """
    return actual is expected or bool(actual == expected)


def stable_order[T](items: list[T], /) -> list[T]:
    """Impose an order on items that have none, so two runs read the same.

    Sets are unordered and CPython's iteration order for strings depends on the
    hash seed, which would make a failure message differ between runs of the same
    test. Mixed or unorderable items keep iteration order -- an arbitrary order
    beats an exception raised while rendering somebody else's failure.

    Exported from the package rather than kept to it: ``_collection`` renders the
    same kind of container in the same kind of message and needs the same answer,
    and two implementations free to drift would eventually give a reader two
    different orders for one collection.

    ``Exception`` rather than ``TypeError``, matching the twin in
    ``_equivalence.py``, because a ``__lt__`` is somebody else's code and may
    raise whatever it likes. Narrowed to ``TypeError``, a set of hostile members
    costs the reader the *entire* difference block: the exception escapes to the
    guard in :func:`describe_difference`, which degrades to ``""``, and the
    message is two reprs and nothing else. Giving up on the order must not mean
    giving up on the items.
    """
    try:
        return sorted(cast("list[Any]", items))
    # Unorderable items keep the order they came in.
    except Exception:
        return items


def is_plain_sequence(value: object, /) -> TypeIs[Sequence[object]]:
    """A sequence whose items are what the reader means by items.

    ``str`` has its own describer, and iterating ``bytes`` yields integers -- a
    diff of those would report positions in a value nobody indexed by hand.
    """
    return isinstance(value, Sequence) and not isinstance(
        value, str | bytes | bytearray | memoryview
    )


def render_operand(value: object, /) -> str:
    """Render one side of an equality failure, clipped to the same budget as a diff.

    ``is_equal_to`` prints both operands before the difference block. A bare
    ``repr`` there undoes everything this module does about size: two large
    collections print in full, and the reader scrolls past both of them to reach
    the few lines that say where they part company. Clipped, the operands stay a
    sanity check on *what* was compared, and the block explains how they differ.

    Rendering goes through the formatter registry, so a domain type with a
    registered formatter reads as itself here rather than as its address. Clipping
    stays outside it: the budget belongs to this message, not to the formatter.
    """
    return clip(format_value(value))
