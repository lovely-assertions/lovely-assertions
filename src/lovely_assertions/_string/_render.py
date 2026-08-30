"""Getting a string into a message without the message becoming the problem.

Every one of these is bounded by the scope the reader is in, and every one of
them runs on the failure path only. A preview that ran long would bury the
sentence it was meant to support; one that clipped from the start would show two
identical openings of two strings that differ in the middle.
"""

from typing import TYPE_CHECKING

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._formatting import current_formatting
from lovely_assertions._text import length_note

if TYPE_CHECKING:
    from collections.abc import Sequence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def clipped(text: str, /) -> str:
    """Render a string for a failure message, eliding an over-long one.

    Failure path only, which is what makes the ``ContextVar`` read affordable: the
    budget is ``max_chars`` from :func:`current_formatting`, so a
    ``formatting(max_chars=...)`` block widens every string in every message this
    module builds without a bound being threaded through every assertion here.

    Rendered through :func:`format_value` rather than ``repr``, so a registered
    ``str`` formatter reaches these messages too; with none registered the two
    are the same call. The elision runs first, on the text, so the formatter is
    handed what will actually be shown: the ``...`` sits inside the rendering
    instead of dangling after it, and ``max_chars`` counts the subject's own
    characters rather than the quotes and escapes a rendering adds to them.

    Assembled by concatenation rather than an f-string, which throughout this
    library marks the one finished message handed to ``_fail`` rather than a
    fragment on its way into one.
    """
    limit = current_formatting().max_chars
    if len(text) <= limit:
        return format_value(text)
    return format_value(text[:limit] + "...") + length_note(len(text))


def clipped_end(text: str, /) -> str:
    """:func:`clipped`, but keeping the end of the string rather than its start.

    Used by the ``ends_with`` family: showing the first line of a long document
    to explain what its last characters are would answer a question nobody asked.
    """
    limit = current_formatting().max_chars
    if len(text) <= limit:
        return format_value(text)
    return format_value("..." + text[-limit:]) + length_note(len(text))


def preview(values: "Sequence[str]", /) -> str:
    """Render the values a multi-value assertion was given, or found, or missed.

    Failure path only. Each value goes through :func:`clipped` and the list
    itself is capped, because both dimensions run away: ``contains_all(*fields)``
    is routinely called with a computed list, and echoing a hundred of them --
    or one of them a page long -- back at the reader helps nobody.
    """
    limit = current_formatting().max_items
    shown = [clipped(value) for value in values[:limit]]
    if len(values) <= limit:
        return "[" + ", ".join(shown) + "]"
    return "[" + ", ".join(shown) + ", ... " + str(len(values) - limit) + " more]"


def clipped_around(text: str, index: int, /) -> str:
    """:func:`clipped`, keeping the window around ``index`` rather than the start.

    Naming the character that broke a character-class assertion is only half an
    answer if the elision cut it out of the rendering: a stray tab at index 400
    of a document would otherwise be reported beside the document's first line.
    """
    limit = current_formatting().max_chars
    if len(text) <= limit:
        return format_value(text)
    start = max(0, min(index - limit // 2, len(text) - limit))
    window = text[start : start + limit]
    if start:
        window = "..." + window
    if start + limit < len(text):
        window += "..."
    return format_value(window) + length_note(len(text))


def at(index: int, /) -> str:
    """The `` at index N`` tail that every offending-character clause ends with."""
    return " at index " + str(index)
