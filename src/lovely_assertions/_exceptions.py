"""The public exception type.

Kept in a module of its own so that ``except AssertionFailure`` can be imported
without dragging in the assertion machinery.
"""

__all__ = ["AssertionFailure", "hide_internal_frames"]


class AssertionFailure(AssertionError):  # noqa: N818  (a test failure, not a program error)
    """Raised when an assertion fails.

    Derives from :class:`AssertionError` so that pytest and unittest treat it as
    an ordinary test failure rather than an error, and named ``Failure`` for the
    same reason: what it reports is an expectation about a value that did not
    hold, which is a result the runner already knows how to present.

    **Its module is the package, not this file**, and that is worth every
    character it saves on the line most people actually read. pytest's short
    summary -- the ``FAILED test_x - ...`` line, which is what a CI log shows and
    what the terminal shows last -- prints ``module.Class: message`` truncated to
    the width of the terminal. A rewritten bare ``assert`` gets its prefix
    stripped by pytest and reads ``assert 4 == 3``; a custom ``AssertionError``
    subclass does not, so the private module path would fill that line on its
    own::

        FAILED test_one - lovely_assertions._excepti...

    Not one character of the message, on a library whose whole claim is the
    message. ``lovely_assertions.AssertionFailure`` is no fiction either: it is
    the name the class is exported under and the path ``pickle`` resolves it by.
    """

    __module__ = "lovely_assertions"
    __slots__ = ()


def hide_internal_frames(excinfo: object = None, /) -> bool:
    """Whether pytest should fold this library's frames out of a traceback.

    Assigned to ``__tracebackhide__`` at module level in every module of the
    package. pytest reads that name from a frame's globals as well as its locals,
    so one assignment per module hides every frame from it -- no decorator, no
    per-method line, and nothing at all on the happy path.

    It is a callable rather than ``True`` because the two cases want opposite
    answers. For an :class:`AssertionFailure` the library's frames are noise: the
    reader wants their own failing line and the message, and three frames of
    engine plus a source listing of the reporting primitive bury both. For
    anything else -- a ``TypeError`` from a bug in here -- those same frames are
    the only thing worth reading, so they stay.
    """
    if excinfo is None:
        return True
    value = getattr(excinfo, "value", None)
    return isinstance(value, AssertionFailure)
