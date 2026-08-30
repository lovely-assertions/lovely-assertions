"""The numbers a message is allowed to reach, and what makes one usable.

Two kinds of number live here and they are not interchangeable. The defaults are
what a caller who opens no scope gets; the minimums are what a caller who opens
one may not go below, because a limit of zero items or one character produces a
message that is bounded and says nothing.

A limit is validated where it is *written* rather than where it is read. A caller
who asks for a negative width has made a mistake in the test, and reporting it at
the line that made it costs them a moment -- reporting it later, inside a failure
message, costs them the failure they were actually reading.
"""

from typing import Final

from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Items shown from one collection before a rendering says how many it left out.
#: Few enough to read as a clause taken in at a glance; past that the message is
#: skimmed rather than read.
DEFAULT_MAX_ITEMS: Final = 10


#: Characters of any one rendered value, or of one line of a unified diff. About a
#: line of a modern terminal.
DEFAULT_MAX_CHARS: Final = 120


#: Lines of unified diff before it is truncated. Larger than the item bound
#: because a diff is read as a block rather than as a clause inside a sentence,
#: and small enough that the block still sits next to the failing test instead of
#: scrolling it off the screen.
DEFAULT_MAX_DIFF_LINES: Final = 20


#: Levels of nested structure a *difference* descends into -- the value under a
#: key, and the value under a key of that. It is the bound in ``_diff``, not
#: the separate re-entry guard in ``_formatters.py``: that one bounds recursion
#: through user code and is a safety limit rather than a legibility one.
DEFAULT_MAX_DEPTH: Final = 2


#: The smallest ``max_depth`` worth accepting. Zero is meaningful and occasionally
#: what somebody wants: describe this value, do not descend into it. The other
#: three bound how much of *something* is shown, so zero there is a message that
#: reports a failure and then says nothing about it.
MIN_DEPTH: Final = 0


#: The smallest value the three "how much is shown" bounds accept.
MIN_SHOWN: Final = 1


def checked(name: str, value: object, minimum: int, /) -> int:
    """Validate one limit, or say which one was wrong and why.

    Takes ``object`` rather than ``int`` so the check means something: against the
    declared type it would be a tautology, and this is the boundary where a
    caller's declaration might be wrong (``_formatters._check_class`` takes the
    same line for the same reason).

    The type check earns its place. A limit that is not an integer does not fail
    here -- it fails later, inside a slice, while a *failing test* is being
    reported, turning somebody's assertion failure into a ``TypeError`` raised in
    the assertion library. That is the worst outcome available, and it is a long
    way from the call that caused it.
    """
    if not isinstance(value, int):
        message = name + " must be an integer, not " + type(value).__name__
        raise TypeError(message)
    if value < minimum:
        message = name + " must be at least " + str(minimum) + ", not " + str(value)
        raise ValueError(message)
    return value


def checked_override(name: str, value: object, minimum: int, /) -> int | None:
    """:func:`checked` for an override, where ``None`` means "leave this one alone"."""
    if value is None:
        return None
    return checked(name, value, minimum)


def immutable(action: str, name: str, /) -> str:
    """The message behind a refused mutation."""
    return (
        "cannot "
        + action
        + " "
        + name
        + " on FormattingOptions: it is immutable."
        + " Derive a modified copy with .replace(...) instead."
    )
