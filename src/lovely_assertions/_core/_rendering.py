"""Laying collected failure sentences out as text.

Four shapes, one per way failures arrive: a bullet for one of many, numbered
alternatives for the branches of an OR, findings for what an inspector said, and
the aggregate a soft scope reports at its end.

All of it runs after something has already failed, so the rules the assertion
bodies obey do not apply here -- but the bound does. A report that prints a
thousand failures is a report nobody reads.
"""

from typing import TYPE_CHECKING

from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Sequence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def _render_bullet(item: str, bullet: str, indent: str, /) -> list[str]:
    """One collected failure as a bullet, its own detail block indented under it.

    The full stop comes off the *sentence*, which is the first line and nothing
    else. Taking it off the whole message only ever reaches the last line, so a
    finding carrying a difference block would keep the full stop that a one-line
    finding beside it had just lost.
    """
    head, newline, block = item.partition("\n")
    lines = [bullet + head.removesuffix(".")]
    if newline:
        lines.extend(indent + line for line in block.splitlines())
    return lines


def render_alternative(index: int, collected: list[str], /) -> str:
    """One branch's findings, indented under a numbered heading."""
    lines = ["  alternative " + str(index) + ":"]
    for item in collected:
        lines.extend(_render_bullet(item, "    - ", "      "))
    return "\n".join(lines)


def render_findings(collected: list[str], /) -> str:
    """Lay collected failures out as a list, keeping each one's own block with it.

    A nested failure can run to several lines -- a difference block, most often --
    and the continuation lines have to sit under their bullet rather than flush
    against the margin, or the reader cannot tell which finding they belong to.
    ``render_aggregate`` does the same for a soft scope.
    """
    lines: list[str] = []
    for item in collected:
        lines.extend(_render_bullet(item, "  - ", "    "))
    return "\n".join(lines)


def render_aggregate(failures: list[str]) -> str:
    """Build the message a soft scope raises on the way out."""
    count = len(failures)
    noun = "assertion" if count == 1 else "assertions"
    lines = [f"{count} {noun} failed:"]
    for index, message in enumerate(failures, 1):
        # A message may run to several lines; its continuation is indented to sit
        # under the numbered item rather than under the list.
        head, newline, block = message.partition("\n")
        lines.append(f"  ({index}) {head}")
        if newline:
            lines.extend(f"      {line}" for line in block.splitlines())
    return "\n".join(lines)


#: The singular form, because "1 assertions" reads as a message nobody looked at
#: -- the same rule :func:`~lovely_assertions._text.count_of` exists for.
_NOTED_HEADING = "1 assertion had already failed in this scope:"


def note_collected(error: BaseException, collected: "Sequence[str]", /) -> None:
    """Attach a scope's collected failures to the error that cut it short.

    Called only when something is already propagating out of the block, so it
    must not raise and must not change what propagates. ``add_note`` does
    neither: it appends to a list the traceback machinery prints under the
    exception, and every renderer that matters -- CPython's own and pytest's --
    shows it.
    """
    if not collected:
        return
    error.add_note(
        _NOTED_HEADING
        if len(collected) == 1
        else str(len(collected)) + " assertions had already failed in this scope:"
    )
    for position, failure in enumerate(collected, 1):
        # The head already ends in its full stop; a failure with a detail block
        # keeps it on the first line, which is where the sentence ends.
        head, newline, block = failure.partition("\n")
        error.add_note("  (" + str(position) + ") " + head)
        if newline:
            for line in block.splitlines():
                error.add_note("      " + line)
