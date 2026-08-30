"""The one question this package answers, and the two halves that answer it.

Given the frame an assertion failed in, name the expression the reader wrote.
The stack half finds whose frame to look at; the source half finds what was
written there. Both run on the failure path and nowhere else -- a passing
assertion never reaches this module, which is the whole reason the work here is
allowed to be as expensive as it is.
"""

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._names._expressions import subject_expression
from lovely_assertions._names._frames import caller_frame

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Rendered in place of the subject name when the expression cannot be recovered
#: unambiguously.
FALLBACK_SUBJECT_NAME = "the value"


def resolve_subject_name() -> str | None:
    """Recover the source text of the current subject's expression.

    Returns ``None`` when the caller cannot be located, the source is
    unavailable, the statement contains anything other than exactly one
    subject-building call, or that one call was handed no positional argument:
    a subject that supplies its own value has no expression to be named by.

    **And when anything at all goes wrong**, which is the point of the guard
    rather than an apology for it. Everything below this line is a nicety: the
    caller has already failed an assertion, the message is already written, and
    all this adds is the name the reader wrote instead of
    :data:`FALLBACK_SUBJECT_NAME`. There is no failure here worth more than that
    message, and two of them cost far more.

    Unguarded, an exception raised while recovering a name *replaces* the
    ``AssertionFailure`` -- the reader is shown a traceback from this module
    where their own assertion's account of what went wrong should be. Inside a
    soft scope it is worse: the exception leaves
    :meth:`~lovely_assertions.SoftScope.__exit__` by the wrong door and every
    failure collected before it is discarded, so a block that found four
    problems reports none of them and one unrelated error.

    The rest of this module is already written as a sequence of ways to give up.
    This is the last of them, and the only one that has to hold whatever the
    interpreter is doing: ``ast.parse`` raises ``RecursionError`` rather than
    ``SyntaxError`` on deeply nested generated source, ``linecache`` can hand
    back a file that has been rewritten since the frame was captured, and a
    subject built inside ``exec`` has a filename that names nothing at all.
    """
    try:
        frame = caller_frame()
        if frame is None:
            return None
        return subject_expression(frame)
    # A name is never worth an assertion's message.
    except Exception:
        return None
