"""Running ``difflib``, and bounding what it is allowed to cost.

``difflib``'s matching cost grows with the square of the number of *changed*
lines, and this code runs while a test is already failing. Time spent here is
indistinguishable, to the person waiting on it, from a hung test run.

So the identical head and tail are trimmed off before ``difflib`` sees anything,
which is both cheaper and better: the reader is shown the changed middle rather
than a screen of context. What is left is capped outright, because a bound the
caller could raise is a bound that cannot protect them.
"""

from typing import Final

from lovely_assertions._diff._clipping import clip_diff_lines
from lovely_assertions._diff._hunks import shift_hunk
from lovely_assertions._diff._primitives import INDENT, indentation
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatting import current_formatting
from lovely_assertions._text import count_of

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Lines of each text handed to ``difflib`` once the identical head and tail are
#: off. Its matching cost grows with the square of the number of *changed* lines,
#: so two long texts that differ throughout can spend many seconds to yield the
#: handful of lines this prints -- and time spent inside a failing assertion is
#: indistinguishable, to the person waiting on it, from a hung test run. Capping
#: the input caps that cost whatever the two texts hold.
_MAX_DIFF_INPUT: Final = 2000


#: Lines of unchanged text a unified diff prints around a change -- ``difflib``'s
#: own default, named here because the windowing has to leave at least this many
#: identical lines on each side of one or it would change the hunks themselves.
_DIFF_CONTEXT: Final = 3


def unified_diff(actual_lines: list[str], expected_lines: list[str], depth: int, /) -> list[str]:
    """``difflib``'s unified diff over a bounded window, indented and labelled.

    The ``---``/``+++`` header is dropped and replaced by one line naming the two
    sides, because at 6pm nobody should have to remember which of the two markers
    means which. Hunk headers stay, and stay whole at any bound: in a long text
    they are the line numbers, and :func:`shift_hunk` puts back the numbers the
    windowing took off.

    ``difflib`` is never handed the whole text -- see :data:`_MAX_DIFF_INPUT`.
    """
    import difflib  # noqa: PLC0415  (importing this package must not import difflib)

    max_diff_lines = current_formatting().max_diff_lines
    start, actual_core, expected_core = _diff_window(actual_lines, expected_lines)
    capped = max(len(actual_core), len(expected_core)) > _MAX_DIFF_INPUT
    if capped:
        actual_core = actual_core[:_MAX_DIFF_INPUT]
        expected_core = expected_core[:_MAX_DIFF_INPUT]
    paired = difflib.unified_diff(expected_core, actual_core, lineterm="", n=_DIFF_CONTEXT)
    body = list(paired)[2:]
    # Insurance for the windowing rather than a case this caller can reach: the
    # first line the two texts disagree on always sits within the context of the
    # window's start and so within the input cap, leaving `difflib` a hunk to emit.
    if not body:
        return []
    indent = indentation(depth)
    inner = indent + INDENT
    lines = [indent + "the strings differ (- expected, + actual):"]
    lines.extend(inner + shift_hunk(text, start) for text in clip_diff_lines(body, max_diff_lines))
    if capped:
        # The elided count would be a number about the window, not about the
        # texts, and a precise-looking wrong number is worse than no number.
        lines.append(
            inner + "... (more diff lines; only " + str(_MAX_DIFF_INPUT) + " lines were compared)"
        )
        return lines
    elided = len(body) - max_diff_lines
    if elided > 0:
        lines.append(inner + "... (" + count_of(elided, "more diff line") + ")")
    return lines


def _diff_window(
    actual_lines: list[str], expected_lines: list[str], /
) -> tuple[int, list[str], list[str]]:
    """The slice of both texts the diff has to look at, and the line it starts on.

    Identical lines further out than the context a unified diff prints cannot
    change a hunk -- only how long ``difflib`` spends deciding that they match.
    Dropping them costs one linear scan where the matching is quadratic, and the
    line numbers they carried are restored by :func:`shift_hunk`.
    """
    head = _common_head(actual_lines, expected_lines)
    tail = _common_tail(actual_lines, expected_lines, head)
    start = max(0, head - _DIFF_CONTEXT)
    return (
        start,
        actual_lines[start : len(actual_lines) - tail + _DIFF_CONTEXT],
        expected_lines[start : len(expected_lines) - tail + _DIFF_CONTEXT],
    )


def _common_head(actual: list[str], expected: list[str], /) -> int:
    """How many leading lines the two texts share."""
    limit = min(len(actual), len(expected))
    index = 0
    while index < limit and actual[index] == expected[index]:
        index += 1
    return index


def _common_tail(actual: list[str], expected: list[str], head: int, /) -> int:
    """How many trailing lines they share, without counting the head twice."""
    limit = min(len(actual), len(expected)) - head
    index = 0
    while index < limit and actual[-1 - index] == expected[-1 - index]:
        index += 1
    return index
