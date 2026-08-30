"""Comparing two strings, which is the case a reader is fussiest about.

Two decisions, in that order. A budget on the two ``repr``\\ s together decides
whether this file says anything at all: the caller has already printed both, and
pointing at a column of something already legible in full helps nobody. Then the
line count decides the form -- multi-line text gets a unified diff, and a single
line gets the column where the two part company, because a diff of one line
against one line is two lines the reader has already read.

The line-ending case is the one that justifies the file. Two strings that differ
only in ``\r\n`` versus ``\n`` print identically, and a diff of them is a reader
staring at two lines they cannot tell apart. It is named in words instead.
"""

from typing import Final

from lovely_assertions._diff._primitives import (
    CONTEXT_CHARS,
    clip,
    common_prefix_length,
    indentation,
)
from lovely_assertions._diff._unified import unified_diff
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Combined ``repr`` length under which two strings are simply read side by side.
#: The message carrying this block prints both already; under this budget the pair
#: still fits on one terminal line, and pointing at a column of a fourteen-
#: character string is noise, not help.
TEXT_BUDGET: Final = 40


def describe_text(actual: str, expected: str, depth: int, /) -> list[str]:
    """A unified diff for multi-line strings, a column for single-line ones.

    Multi-line is where ``but was 'line1\\nline2\\n...'`` stops being a message and
    becomes a puzzle, so that is where the diff earns its import. Short strings get
    nothing: the caller already printed both, and two twelve-character reprs on one
    line are read faster than any diff of them.
    """
    if len(format_value(actual)) + len(format_value(expected)) <= TEXT_BUDGET:
        return []
    actual_lines = actual.splitlines()
    expected_lines = expected.splitlines()
    if len(actual_lines) <= 1 and len(expected_lines) <= 1:
        return [indentation(depth) + _first_text_difference(actual, expected)]
    if actual_lines == expected_lines:
        ending = _line_ending_difference(actual, expected)
        # Nothing to name here means the two texts are the same string, so the
        # difference is in what `__eq__` did with them. Declining hands the pair
        # on to `describe_look_alike`, which is where that finding is worded.
        return [] if ending is None else [indentation(depth) + ending]
    return unified_diff(actual_lines, expected_lines, depth)


def _first_text_difference(actual: str, expected: str, /) -> str:
    """Where two single-line strings part company, and on what.

    The index is quoted with the tail of the common prefix rather than a caret
    under the text: the message renders strings through ``repr``, where an escape
    sequence occupies several columns, so a caret would point at the wrong one for
    exactly the strings -- tabs, newlines, non-ASCII -- that need it most.
    """
    shared = common_prefix_length(actual, expected)
    if shared == len(actual):
        return (
            "the first "
            + str(shared)
            + " characters match; actual ends there, expected continues with "
            + clip(repr(expected[shared:]))
        )
    if shared == len(expected):
        return (
            "the first "
            + str(shared)
            + " characters match; expected ends there, actual continues with "
            + clip(repr(actual[shared:]))
        )
    return (
        "first difference at index "
        + str(shared)
        + ": "
        + format_value(actual[shared])
        + " instead of "
        + format_value(expected[shared])
        + _after_clause(actual, shared)
    )


def _line_ending_difference(actual: str, expected: str, /) -> str | None:
    """Name the line whose terminator differs, or ``None`` when none of them does.

    A diff of two texts with identical lines is empty, so without this the reader
    would be told the strings differ and shown no difference at all -- the worst
    possible message for the one bug that is invisible in a terminal.

    ``None`` is the other half of that promise. Falling out of the loop means
    every line matched its counterpart down to the terminator, so the two texts
    are the same string and their line endings are precisely what does *not*
    differ -- a ``str`` subclass whose ``__eq__`` answers no is how a pair gets
    here. The caller has a clause for that; this function must not invent one.
    """
    actual_lines = actual.splitlines(keepends=True)
    expected_lines = expected.splitlines(keepends=True)
    for number, (left, right) in enumerate(zip(actual_lines, expected_lines, strict=False), 1):
        if left != right:
            return (
                "the lines are identical; line "
                + str(number)
                + " ends with "
                + _terminator(left)
                + ", not "
                + _terminator(right)
            )
    return None


def _terminator(line: str, /) -> str:
    """``"'\\r\\n'"`` or ``"no newline"`` -- how one line of text ends.

    The terminator is whatever ``splitlines`` broke on, not just ``\\r`` and
    ``\\n``: Python also breaks a string on a form feed, a vertical tab, U+2028
    and four more. Stripping a fixed set of characters instead would call every
    one of those "no newline", which is the one claim this message exists to make
    and the one it must never get wrong.
    """
    content = line.splitlines()[0] if line else ""
    if len(content) == len(line):
        return "no newline"
    return repr(line[len(content) :])


def _after_clause(text: str, index: int, /) -> str:
    """Quote the tail of the common prefix, so the reader can search for it."""
    if index == 0:
        return ""
    start = max(0, index - CONTEXT_CHARS)
    leader = "..." if start > 0 else ""
    return ", after " + leader + repr(text[start:index])
