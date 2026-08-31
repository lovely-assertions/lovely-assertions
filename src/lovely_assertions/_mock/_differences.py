"""Why a call did not match, which is the half a reader needs.

"No call matched" is true and useless. These say which call came closest, what
differed about it, and whether an earlier one matched something the assertion was
not asking about -- three findings that send the reader to three different bugs.
"""

from typing import TYPE_CHECKING, Any

from lovely_assertions import _engine
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._mock._call_matching import matches_call
from lovely_assertions._mock._rendering import (
    INDENT,
    call_numbers,
    render_options,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def describe_call_difference(
    recorded: "Sequence[Any]", args: "tuple[object, ...]", kwargs: "Mapping[str, object]", /
) -> str:
    """How a recorded call differs from the one that was expected.

    The whole point of routing this through
    :func:`~lovely_assertions._diff.describe_difference` rather than printing two
    argument lists: one wrong keyword out of six is reported as *that keyword*,
    the way a mapping comparison reports it, instead of leaving the reader to
    diff two lines by eye.

    Each half is asked only when it actually differs. ``describe_difference`` is
    written for two values that are already known to be unequal, and given two
    equal ones it would report -- correctly for its own contract, absurdly here --
    that they render alike and are not equal.
    """
    block = ""
    if recorded[-2] != args:
        positional = _engine.describe_difference(recorded[-2], args)
        if positional:
            block += "\n" + INDENT + "positional arguments:" + _deepen(positional)
    if recorded[-1] != kwargs:
        keyword = _engine.describe_difference(recorded[-1], kwargs)
        if keyword:
            block += "\n" + INDENT + "keyword arguments:" + _deepen(keyword)
    return block


def _deepen(block: str, /) -> str:
    """Indent a nested block one level under the line that introduces it."""
    return block.replace("\n", "\n" + INDENT)


def earlier_matches_note(
    recorded: "Sequence[Any]", args: "tuple[object, ...]", kwargs: "Mapping[str, object]", /
) -> str:
    """Name the earlier calls that matched, when ``was_called_with`` failed on the last.

    This is the line ``assert_called_with`` never prints and the reader always
    needs. "Expected: fetch('/users') / Actual: fetch('/other')" sends somebody
    hunting for a call that is right there in the recording -- it was simply not
    the last one, and that is a fact about the assertion rather than about the
    code under test.
    """
    matched = [
        index for index, one in enumerate(recorded[:-1], 1) if matches_call(one, args, kwargs)
    ]
    if not matched:
        return ""
    options = render_options()
    return (
        "\n"
        + INDENT
        + call_numbers(matched, options)
        + (" was" if len(matched) == 1 else " were")
        + " made with those arguments; only the last call is checked"
    )


def which_matched(
    recorded: "Sequence[Any]", args: "tuple[object, ...]", kwargs: "Mapping[str, object]", /
) -> str:
    """Which of several calls matched, for a failed ``was_called_once_with``.

    "Called 3 times" leaves two very different bugs looking identical: the code
    called the right thing three times when it should have called it once, or it
    called three different things and none of them was right. This line says
    which.
    """
    matched = [index for index, one in enumerate(recorded, 1) if matches_call(one, args, kwargs)]
    options = render_options()
    if not matched:
        return "\n" + INDENT + "none of those calls was made with those arguments"
    return (
        "\n"
        + INDENT
        + call_numbers(matched, options)
        + (" was" if len(matched) == 1 else " were")
        + " made with those arguments; it is the call count that is wrong"
    )


def nearest_note(
    recorded: "Sequence[Any]", args: "tuple[object, ...]", kwargs: "Mapping[str, object]", /
) -> str:
    """Explain the recorded call that came closest to the one that was expected.

    A heuristic, and only ever a choice of *which* call to explain -- it decides
    nothing about whether the assertion passed. The distance is the number of
    argument slots that disagree: positions that hold different values, positions
    one side does not have at all, keywords only one side passed, and keywords
    both passed with different values. The first call with the lowest score wins,
    so a tie keeps the order the calls were made in.
    """
    nearest = 0
    best = -1
    for index, one in enumerate(recorded):
        score = distance(one, args, kwargs)
        if best < 0 or score < best:
            nearest, best = index, score
    difference = describe_call_difference(recorded[nearest], args, kwargs)
    if not difference:
        return ""
    return "\n" + INDENT + "the closest was call " + str(nearest + 1) + ":" + _deepen(difference)


def distance(
    recorded: "Sequence[Any]", args: "tuple[object, ...]", kwargs: "Mapping[str, object]", /
) -> int:
    """How many argument slots one recorded call disagrees with the expected one in."""
    recorded_args: Sequence[Any] = recorded[-2]
    recorded_kwargs: Mapping[str, Any] = recorded[-1]
    score = abs(len(recorded_args) - len(args))
    score += sum(1 for left, right in zip(recorded_args, args, strict=False) if left != right)
    score += len(set(recorded_kwargs).symmetric_difference(kwargs))
    score += sum(
        1 for name, value in recorded_kwargs.items() if name in kwargs and value != kwargs[name]
    )
    return score
