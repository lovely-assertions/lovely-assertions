"""Rendering an exception, its cause and its notes for a message.

Bounded like everything else that runs on a failure path, and total: an exception
whose ``str`` raises still has to produce a sentence, because the assertion that
caught it already failed and a second failure on the way out would replace a
readable message with a traceback into this library.

The cause chain is followed one link, not all of them. ``raise B from A`` is the
link a reader means; the rest is the history of how the exception travelled.
"""

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._text import length_note

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Longest rendering kept in full in a failure message. An exception message can
#: be a whole serialised payload, and a message that dumps one hides the finding
#: instead of explaining it. 120 characters is about a terminal line, the same cap
#: the string subject uses.
_MAX_RENDERED = 120


#: Where :func:`cause_of` found what it found, named as the reader will see it in
#: a traceback. ``SUPPRESSED`` is the ``raise ... from None`` case: there is a
#: ``__context__``, and the author of the code said not to treat it as the cause.
_FROM_CAUSE = "__cause__"


_FROM_CONTEXT = "__context__"


SUPPRESSED = "suppressed"


_NO_CAUSE = "none"


#: Longest run of notes listed in a failure message, matching the collection
#: subject's budget. A retry loop that adds a note per attempt can attach a great
#: many, and a message that dumps all of them hides the finding instead of
#: explaining it.
_MAX_NOTES = 10


# ---------------------------------------------------------------------------
# Helpers -- failure path only.
#
# No f-strings here: an f-string is a message, and a message is only ever built
# inside the `_fail` call itself, so a passing assertion formats nothing.
# ---------------------------------------------------------------------------
def rendered(value: object, /) -> str:
    """Render a value for a failure message, eliding an over-long one.

    One helper for exceptions, messages, notes and return values alike, and all
    of them go through :func:`~lovely_assertions.format_value`, so a project that
    registered a formatter for its own exception type reads it here as it reads
    it everywhere else. When nothing claims the value the rendering is its
    ``repr``, so a message keeps its quotes and an exception keeps its type.

    A ``str`` nothing claimed is clipped *before* it is rendered, which is how
    the string subject does it. Clipping the rendering instead cuts the closing
    quote -- or the middle of an escape sequence -- in half, and counts the two
    quotes towards the length it reports back, so a 300-character message would
    be reported as 302 characters long. Everything else is clipped after, because
    a partial rendering is the only one such a value has.

    A hostile ``__repr__`` costs the reader detail and nothing more:
    ``format_value`` describes such a value by its type rather than raising. That
    is the contract this needs, not laziness -- the assertion has *already*
    failed, and an error thrown while reporting it would also throw away the
    ``__cause__`` that was about to explain it.
    """
    text = format_value(value)
    # A rendering identical to the `repr` means the registry declined, so the
    # careful clip below applies to a string this module is rendering itself. A
    # formatter that did claim it owns the rendering, which is clipped like any
    # other.
    if isinstance(value, str) and text == repr(value):
        if len(value) <= _MAX_RENDERED:
            return text
        return repr(value[:_MAX_RENDERED] + "...") + length_note(len(value))
    if len(text) <= _MAX_RENDERED:
        return text
    return text[:_MAX_RENDERED] + "..." + length_note(len(text))


def cause_of(exception: BaseException, /) -> tuple[BaseException | None, str]:
    """The exception's cause, and the name of the attribute it came from.

    ``__cause__`` wins over ``__context__``: it is the one the code stated
    explicitly with ``raise X from Y``, where ``__context__`` is whatever
    happened to be in flight. ``raise X from None`` is honoured as the denial it
    is -- the context is still there, but reporting it as the cause would
    contradict the code -- and is reported as suppressed rather than as absent.
    """
    cause = exception.__cause__
    if cause is not None:
        return cause, _FROM_CAUSE
    context = exception.__context__
    if context is None:
        return None, _NO_CAUSE
    if exception.__suppress_context__:
        return None, SUPPRESSED
    return context, _FROM_CONTEXT


def notes_of(exception: BaseException, /) -> "list[str] | None":
    """The exception's PEP 678 notes, or ``None`` when it has none.

    ``__notes__`` does not exist until the first ``add_note``, so this is a
    ``getattr`` with a default rather than an attribute access -- an exception
    with no notes is the ordinary case, not an error to catch.

    The annotation is what typeshed and PEP 678 promise, and the ``isinstance``
    is what actually holds: CPython's ``add_note`` refuses to append to anything
    that is not a ``list``, so a ``__notes__`` of some other shape was never
    built by the documented API. It also catches the one value the library itself
    can put there -- the stand-in a soft scope hands back after a failed
    ``expect_raises``, whose every attribute is itself. Iterating that would raise
    a ``TypeError`` from inside a soft block and cost the scope its whole report.
    """
    notes: list[str] | None = getattr(exception, "__notes__", None)
    return notes if isinstance(notes, list) else None


def render_notes(notes: "list[str] | None", /) -> str:
    """Describe the notes an exception carried. Failure path only.

    The listing is the point of these messages. "No note matched" is a fact the
    reader already had; *which* notes were there is the one they have to go and
    look up otherwise, and PEP 678 notes exist precisely because they carry the
    context that explains the failure.
    """
    if not notes:
        return "it carried no notes"
    if len(notes) == 1:
        return "its only note was " + rendered(notes[0])
    shown = ", ".join(rendered(note) for note in notes[:_MAX_NOTES])
    if len(notes) <= _MAX_NOTES:
        return "its notes were " + shown
    return "its notes were " + shown + ", ... (" + str(len(notes) - _MAX_NOTES) + " more)"
