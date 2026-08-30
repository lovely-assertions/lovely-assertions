"""Equality with something deliberately ignored.

Case first, and then whitespace and newline style if the caller asks. Each thing
ignored is named in the failure, because an assertion that passes for a reason
the reader did not intend is worse than one that fails.
"""

from typing import Self

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._string._render import clipped

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def _lf(text: str, /) -> str:
    """``text`` with CRLF and lone-CR line endings rewritten to LF."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def equivalent(subject: str, expected: str, /, *, whitespace: bool, newline_style: bool) -> bool:
    """Whether two strings match once case -- and optionally more -- is set aside.

    ``casefold`` rather than ``lower``: it is the comparison Unicode defines for
    caseless matching, so ``"STRASSE"`` and ``"straße"`` come out equal.

    ``whitespace`` removes whitespace outright, which subsumes the newline-style
    normalisation, hence the early return: ``split()`` with no argument splits on
    runs of any whitespace and drops the empty pieces, so joining the pieces back
    together leaves the text with none.
    """
    if whitespace:
        return "".join(subject.split()).casefold() == "".join(expected.split()).casefold()
    if newline_style:
        return _lf(subject).casefold() == _lf(expected).casefold()
    return subject.casefold() == expected.casefold()


def ignoring(*, whitespace: bool, newline_style: bool) -> str:
    """The ``ignoring ...`` clause naming what an equivalence comparison set aside."""
    parts = ["case"]
    if whitespace:
        parts.append("whitespace")
    if newline_style:
        parts.append("newline style")
    if len(parts) == 1:
        return " ignoring case"
    return " ignoring " + ", ".join(parts[:-1]) + " and " + parts[-1]


class CaselessEqualityAssertions(Expect[str]):
    """Equality once case, and optionally more, is set aside."""

    __slots__ = ()

    def is_equal_ignoring_case(
        self,
        expected: str,
        /,
        *,
        ignoring_whitespace: bool = False,
        ignoring_newline_style: bool = False,
        because: str = "",
    ) -> Self:
        """Assert the string equals ``expected`` once case is set aside.

        ``ignoring_whitespace`` drops whitespace from both sides entirely, which
        covers indentation, wrapping and trailing newlines in one option rather
        than three. ``ignoring_newline_style`` is the narrower tool: it rewrites
        CRLF and CR to LF, so a file read on Windows compares equal to the same
        file read anywhere else, and nothing else moves.
        """
        subject = self._subject
        if equivalent(
            subject,
            expected,
            whitespace=ignoring_whitespace,
            newline_style=ignoring_newline_style,
        ):
            return self
        clause = ignoring(whitespace=ignoring_whitespace, newline_style=ignoring_newline_style)
        return self._fail(
            f"to equal {clipped(expected)}{clause}, but was {clipped(subject)}", because
        )

    def is_not_equal_ignoring_case(
        self,
        unexpected: str,
        /,
        *,
        ignoring_whitespace: bool = False,
        ignoring_newline_style: bool = False,
        because: str = "",
    ) -> Self:
        """Assert the string differs from ``unexpected`` by more than case."""
        subject = self._subject
        if not equivalent(
            subject,
            unexpected,
            whitespace=ignoring_whitespace,
            newline_style=ignoring_newline_style,
        ):
            return self
        clause = ignoring(whitespace=ignoring_whitespace, newline_style=ignoring_newline_style)
        return self._fail(
            f"not to equal {clipped(unexpected)}{clause}, but was {clipped(subject)}", because
        )
