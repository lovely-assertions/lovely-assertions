"""Putting a path, a run of names or a difference into a message.

Failure path only. A path is rendered through the formatter registry like any
other value, so a project that has registered one for its own path type gets it
here too -- and clipped to the scope, because a deeply nested path is a line the
reader has to scan rather than read.
"""

from lovely_assertions._diff import describe_difference
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._formatting import current_formatting
from lovely_assertions._text import length_note

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Longest file content this module will hand to ``_diff`` for a line-by-line
#: difference. The clipped rendering and the invisible-difference note are cheap
#: whatever the size; a unified diff is ``difflib`` over the whole of both sides,
#: and running that across a multi-megabyte fixture would turn one failing
#: assertion into a hang. Past this the message still names the file, shows the
#: first :data:`~lovely_assertions.FormattingOptions.max_chars` of it and says
#: how long it really is.
_MAX_DIFFED = 100_000


def rendered(value: object, /) -> str:
    """Render a path for a failure message. Failure path only.

    A path's ``repr`` is ``PosixPath('/etc/hosts')``; what a reader wants to see
    is ``/etc/hosts``. The formatter registry keeps precedence, so a project that
    has registered its own spelling still gets it.
    """
    text = format_value(value)
    if text != repr(value):
        return text
    return "'" + str(value) + "'"


def clipped(text: str, /) -> str:
    """Render a string operand or a file's contents, eliding an over-long one.

    Failure path only, which is what makes the ``ContextVar`` read affordable.
    The same budget and the same tail as ``_string.clipped``: a file's text and
    a string subject are the same kind of thing to a reader, and two subjects
    that elide the same value at different lengths would only raise the question
    of which one was lying.

    Rendered through the formatter registry rather than with a bare ``repr``, so
    a project that has registered a spelling of its own for text gets it here.
    The budget bounds the *value*, not the rendering of it, so the cut is made
    before the rendering: what the reader sees elided is the text that was too
    long, not the quoting around it.
    """
    limit = current_formatting().max_chars
    if len(text) <= limit:
        return format_value(text)
    return format_value(text[:limit] + "...") + length_note(len(text))


def names_preview(names: "list[str] | tuple[str, ...]", /) -> str:
    """Render a directory listing, or a run of suffixes. Failure path only.

    Capped at ``max_items`` for the reason ``_string._preview`` is: a directory
    with four hundred entries in it answers no question by having all four
    hundred printed at the reader.

    A tuple renders exactly as the list of the same names does. The parameter
    admits one so that :meth:`PurePathExpect.has_suffixes` can show the sequence
    it was handed without copying it into a list first.

    Each name goes through the formatter registry, so one list in one message
    does not render half its entries the library's way and half a project's.
    """
    limit = current_formatting().max_items
    shown = [format_value(name) for name in names[:limit]]
    if len(names) <= limit:
        return "[" + ", ".join(shown) + "]"
    return "[" + ", ".join(shown) + ", ... " + str(len(names) - limit) + " more]"


def suffix_note(suffix: str, /) -> str:
    """``the suffix '.gz'``, or ``no suffix`` for a path that has none. Failure path only.

    Rendered through the formatter registry, as the claimed suffix on the other
    side of the same sentence is: one message must not render the suffix that
    was wanted and the suffix that was found two different ways.
    """
    if not suffix:
        return "no suffix"
    return "the suffix " + format_value(suffix)


def missing_note(actual: str, expected: str, /) -> str:
    """Name a near-miss a substring search would otherwise leave unexplained.

    Failure path only. Text read from a file carries its real line endings, so a
    needle spelled with ``\\n`` misses a CRLF file entirely -- and the two
    renderings look identical unless somebody says why.
    """
    normalised = actual.replace("\r\n", "\n").replace("\r", "\n")
    if expected in normalised:
        return " (the file uses CRLF line endings; the text is there with those)"
    if expected.casefold() in actual.casefold():
        return " (it is there in a different case)"
    return ""


def text_difference(actual: str, expected: str, /) -> str:
    """The line-by-line difference between two file contents. Failure path only.

    Bounded by :data:`_MAX_DIFFED`, because ``difflib`` over a large fixture is
    the one way a failure message here could cost more than the test did.
    """
    if len(actual) > _MAX_DIFFED or len(expected) > _MAX_DIFFED:
        return ""
    return describe_difference(actual, expected)


def invisible_note(actual: str, expected: str, /) -> str:
    """Name a difference the two renderings do not show. Failure path only.

    ``Expected notes to have the text 'hello', but 'hello'`` is the worst message
    this module could produce, and three ordinary situations produce it: a
    byte-order mark, CRLF line endings, and trailing whitespace. Each gets said
    out loud, with the fix where there is one.
    """
    if actual.startswith("﻿") and actual[1:] == expected:
        return " (it starts with a byte-order mark; read it with encoding='utf-8-sig')"
    if actual.replace("\r\n", "\n").replace("\r", "\n") == expected.replace("\r\n", "\n").replace(
        "\r", "\n"
    ):
        return " (the two differ only in their line endings)"
    if actual.strip() == expected.strip():
        return " (the two differ only in surrounding whitespace)"
    return ""
