"""The per-line pass over a finished diff body.

Two jobs, both of which have to happen after the diff exists rather than before.
A hunk header carries line numbers, and the windowing that made the diff cheap
moved every one of them -- so they are put back, or they point at lines the reader
cannot find in the value they were shown.

And a long line is clipped around the point where its counterpart parts company,
not from the start. Clipping from the start is what turns two four-hundred
character strings that differ at column three hundred into two identical previews
and a reader who concludes the library is broken.
"""

from lovely_assertions._diff._hunks import is_hunk_header
from lovely_assertions._diff._primitives import CONTEXT_CHARS, clip, common_prefix_length
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatting import current_formatting

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def clip_diff_lines(body: list[str], limit: int, /) -> list[str]:
    """Cut over-long diff lines down around the point where the pair parts company.

    Clipping a minified line from the start renders two *different* lines
    identically, which is the one thing a diff must never do. Only ``limit`` lines
    are kept, but a counterpart is looked for across the whole body: the line that
    says where a kept line was clipped may itself sit past the cut.

    Hunk headers are exempt, as the heading and the elision count around them
    already are. A header carries no text from either subject -- only the line
    numbers a reader searches by -- so a bound meant to keep a *value* readable
    has nothing to cut there, while cutting one leaves the numbers half-written
    and puts the clip's own "N more characters" where the second range belongs,
    for :func:`shift_hunk` to read back as a line number the text never had.
    """
    max_chars = current_formatting().max_chars
    return [
        line
        if is_hunk_header(line) or len(line) <= max_chars
        else _clip_around(line, _counterpart(body, index))
        for index, line in enumerate(body[:limit])
    ]


def _counterpart(body: list[str], index: int, /) -> str | None:
    """The added line facing this removed one, or the removed line it replaced.

    A unified diff writes a change as *every* removed line followed by *every*
    added one, so the line facing the k-th removal is the k-th addition -- not the
    neighbour. Pairing by adjacency instead faces most of a multi-line change with
    the wrong counterpart, and :func:`_clip_around` then clips from the start,
    where two different minified lines come out as the same run of characters and
    the same ellipsis.
    """
    marker = body[index][:1]
    if marker == "-":
        removed_start = _run_start(body, index, "-")
        added_start = _run_end(body, index, "-")
        return _facing(body, added_start + index - removed_start, "+")
    if marker == "+":
        added_start = _run_start(body, index, "+")
        if added_start == 0 or not body[added_start - 1].startswith("-"):
            return None
        removed_start = _run_start(body, added_start - 1, "-")
        return _facing(body, removed_start + index - added_start, "-")
    return None


def _run_start(body: list[str], index: int, marker: str, /) -> int:
    """First line of the unbroken run of ``marker`` lines containing ``index``."""
    start = index
    while start > 0 and body[start - 1].startswith(marker):
        start -= 1
    return start


def _run_end(body: list[str], index: int, marker: str, /) -> int:
    """One past the last line of that run."""
    end = index + 1
    while end < len(body) and body[end].startswith(marker):
        end += 1
    return end


def _facing(body: list[str], index: int, marker: str, /) -> str | None:
    """``body[index]`` when it exists and carries ``marker``; ``None`` otherwise."""
    if 0 <= index < len(body) and body[index].startswith(marker):
        return body[index]
    return None


def _clip_around(line: str, counterpart: str | None, /) -> str:
    """Keep the window of an over-long diff line that holds the actual difference."""
    if counterpart is None:
        return clip(line)
    marker = line[:1]
    text = line[1:]
    start = max(0, common_prefix_length(text, counterpart[1:]) - CONTEXT_CHARS)
    if start == 0:
        return clip(line)
    window = text[start : start + current_formatting().max_chars]
    dropped = len(text) - start - len(window)
    tail = "" if dropped <= 0 else "... (" + str(dropped) + " more characters)"
    return marker + "... (" + str(start) + " earlier characters) " + window + tail
