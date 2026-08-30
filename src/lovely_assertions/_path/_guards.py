"""Claims no path could satisfy, refused where they were written.

A suffix without its dot matches nothing; a size below zero is not a size. Each
of these is a mistake in the test rather than a fact about the subject, so it
raises where the caller wrote it instead of failing as though the path were at
fault -- a distinction the reader cannot make from a failure message alone.
"""

from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


# ---------------------------------------------------------------------------
# Caller-bug guards -- a claim no subject could satisfy is a bug in the test
# ---------------------------------------------------------------------------
def reject_bare_suffix(suffix: str, /) -> None:
    """Raise ``ValueError`` for a suffix written without its leading dot.

    ``PurePath.suffix`` is either ``""`` or a string beginning with ``.``, so
    ``has_suffix("txt")`` is not a claim that happens to be false about this
    path: it is a claim no path could ever satisfy, which makes it a bug in the
    test rather than a finding about the subject. The library's rule for those
    is ``ValueError``, and the message names the spelling that was meant.

    ``""`` is left alone -- it is what a path with no suffix genuinely reports,
    so the claim is satisfiable. :meth:`PurePathExpect.has_no_suffix` says the
    same thing in words.
    """
    if suffix and not suffix.startswith("."):
        raise ValueError(
            "a suffix carries its leading dot, the way PurePath.suffix reports it:"
            " got " + repr(suffix) + ", did you mean " + repr("." + suffix) + "?"
        )


def reject_bare_string(expected: object, /) -> None:
    """Raise ``TypeError`` for a bare string where a list of suffixes was wanted.

    The checkers already refuse it -- :meth:`PurePathExpect.has_suffixes` is typed
    to make that possible -- so this is the untyped caller's copy of the same
    answer. Without it ``has_suffixes(".tar.gz")`` iterates the string one
    character at a time and reports something about ``'t'``.

    The parameter is ``object`` rather than the operand's own type on purpose:
    mypy knows a ``list`` is never a ``str`` and calls the check unreachable, and
    widening here is the honest way to say "this is for values the annotation
    could not stop".
    """
    if isinstance(expected, str):
        raise TypeError(
            "has_suffixes takes a list of suffixes, not one string: a str would be"
            " read one character at a time; got " + repr(expected)
        )


def reject_unusable_size(size: int, /) -> None:
    """Raise ``ValueError`` for a byte count no file could have."""
    if size < 0:
        raise ValueError("a size in bytes is never negative, got " + str(size))
