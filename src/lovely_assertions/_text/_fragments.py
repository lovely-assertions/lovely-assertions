"""Text questions cheap enough to ask on a passing assertion.

Nothing here compiles anything or touches a regex engine. Each is a scan or a
count over a string the caller already holds, which is what lets an assertion ask
one before it knows whether it is going to fail.
"""

from typing import TYPE_CHECKING

from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    import re

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def holds_every(subject: str, values: "tuple[str, ...]", /) -> bool:
    """Whether every one of ``values`` appears in ``subject``.

    Spelled as a loop rather than ``all(value in subject for value in values)``
    because this runs on the happy path: the tidier spelling allocates a generator
    object on every *passing* call, and a passing assertion is meant to cost a
    comparison and nothing more. ``_collection._none_outside`` answers the same
    question about a collection, as the same loop, for the same reason.
    """
    for value in values:  # noqa: SIM110  (a generator expression would allocate)
        if value not in subject:
            return False
    return True


def holds_any(subject: str, values: "tuple[str, ...]", /) -> bool:
    """Whether at least one of ``values`` appears in ``subject``.

    A loop for the reason :func:`holds_every` gives.
    """
    for value in values:  # noqa: SIM110  (a generator expression would allocate)
        if value in subject:
            return True
    return False


def count_of(total: int, noun: str, /) -> str:
    """``"1 item"`` or ``"4 items"``.

    A message that says "1 items" reads as a message nobody looked at, which is
    a poor advertisement for one whose whole job is to be read.
    """
    if total == 1:
        return "1 " + noun
    return str(total) + " " + noun + "s"


def length_note(length: int, /) -> str:
    """The ``(truncated from N characters)`` tail that follows an elided value."""
    return " (truncated from " + str(length) + " characters)"


def clipped(text: str, limit: int, /) -> str:
    """Cut an over-long rendering down, saying how much was cut.

    One implementation, because two truncation tails in one message that word
    themselves differently only make the reader wonder whether they mean
    different things -- and because a bound that exists in some renderers and not
    others is the shape the collection renderer was missing when a ten-item list
    of long values produced half a megabyte.
    """
    if len(text) <= limit:
        return text
    return text[:limit] + "... (" + str(len(text) - limit) + " more characters)"


def pattern_text(pattern: "str | re.Pattern[str]", /) -> str:
    """The source text of a regex, whether it arrived compiled or not."""
    return pattern if isinstance(pattern, str) else pattern.pattern
