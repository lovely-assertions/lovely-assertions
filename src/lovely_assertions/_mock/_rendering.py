"""Turning recorded calls into message text.

One call, a run of them, and the arguments an assertion asked for. Bounded like
every other rendering, and numbered, because "the third call" is how a reader
talks about a sequence of calls and ``call(x=1)`` on its own is not.
"""

from typing import TYPE_CHECKING, Any

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._formatting import FormattingOptions, current_formatting
from lovely_assertions._text import clipped

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: One level of a message's detail block, matching ``_diff``.
INDENT = "  "


# ---------------------------------------------------------------------------
# Rendering helpers -- failure path only.
#
# None of them may use an f-string: an f-string is a message, and a message is
# only ever built inside the `_fail` call itself, so that a passing assertion
# formats nothing. They concatenate and join instead.
# ---------------------------------------------------------------------------
def render_options() -> "FormattingOptions":
    """The bounds in force. **Failure path only** -- it reads a ``ContextVar``."""
    return current_formatting()


def render_call(recorded: "Sequence[Any]", options: "FormattingOptions", /) -> str:
    """One call's arguments, in the shape they were written at the call site.

    ``('/users', timeout=3)`` -- the parentheses of a call, not of a tuple, which
    is why a single positional argument does not get a trailing comma. Values go
    through ``format_value`` rather than through the call object's own ``repr``,
    so a registered formatter is consulted for an argument the way it is for
    every other value in a message.
    """
    return render_arguments(recorded[-2], recorded[-1], options)


def render_arguments(
    args: "Sequence[Any]", kwargs: "Mapping[str, Any]", options: "FormattingOptions", /
) -> str:
    """:func:`render_call` for a pair that is not a recorded call object."""
    limit = options.max_items
    shown: list[str] = []
    for value in args:
        if len(shown) == limit:
            break
        shown.append(clipped(format_value(value), options.max_chars))
    for name, value in kwargs.items():
        if len(shown) == limit:
            break
        shown.append(name + "=" + clipped(format_value(value), options.max_chars))
    elided = len(args) + len(kwargs) - len(shown)
    if elided > 0:
        shown.append("... (" + str(elided) + " more)")
    return "(" + ", ".join(shown) + ")"


def wanted(args: "tuple[object, ...]", kwargs: "Mapping[str, object]", /) -> str:
    """The arguments an assertion asked for, as they read after "called with".

    ``()`` is correct and reads as nothing at all in the middle of a sentence, so
    the empty call gets words instead: "called with no arguments" is a claim, and
    "called with ()" is a typo waiting to be reported as one.
    """
    if not args and not kwargs:
        return "no arguments"
    return render_arguments(args, kwargs, render_options())


def render_calls(recorded: "Sequence[Any]", options: "FormattingOptions", /) -> str:
    """Every recorded call, truncated like every other collection in a message."""
    limit = options.max_items
    shown: list[str] = []
    for one in recorded:
        if len(shown) == limit:
            break
        shown.append(render_call(one, options))
    elided = len(recorded) - len(shown)
    if elided > 0:
        return "[" + ", ".join(shown) + ", ... (" + str(elided) + " more)]"
    return "[" + ", ".join(shown) + "]"


def last_clause(total: int, /) -> str:
    """``"called with"`` for a single call, ``"last called with"`` for several.

    "last called with" in front of the only call there is reads as though the
    assertion had ignored the others, which is the very confusion these messages
    exist to remove.
    """
    if total == 1:
        return "called with"
    return "last called with"


def call_numbers(indices: list[int], options: "FormattingOptions", /) -> str:
    """``"call 2"`` or ``"calls 1 and 3"`` -- the calls a note is about.

    Numbered from one and in the order they were made, which is the order the
    listing beside them prints, so "call 2" can be counted off it. Truncated like
    every other listing: a mock called a thousand times must not put a thousand
    numbers in a message.
    """
    noun = "call " if len(indices) == 1 else "calls "
    limit = options.max_items
    shown = [str(index) for index in indices[:limit]]
    elided = len(indices) - len(shown)
    if elided > 0:
        return noun + ", ".join(shown) + ", ... (" + str(elided) + " more)"
    if len(shown) == 1:
        return noun + shown[0]
    return noun + ", ".join(shown[:-1]) + " and " + shown[-1]
