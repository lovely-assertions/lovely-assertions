"""ASCII, printable, whitespace -- what a character does rather than what it is.

The three that matter when text is about to cross a boundary: a terminal, a
protocol, a file with an encoding. The failure names the offending character by
position, because these fail on one character in a line the reader can see.
"""

from typing import Self

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._string._faults import class_fault
from lovely_assertions._string._render import clipped

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class EncodingClassAssertions(Expect[str]):
    """How the characters encode and print."""

    __slots__ = ()

    def is_ascii(self, *, because: str = "") -> Self:
        """Assert every character is ASCII (``str.isascii``).

        One of the two exceptions to the empty-string rule: ``"".isascii()`` is
        ``True``, every one of its zero characters being ASCII. The message names
        the first character that is not and where it sits, which is the whole
        question when a non-breaking space or a smart quote has come back from an
        editor.
        """
        subject = self._subject
        if subject.isascii():
            return self
        return self._fail(
            f"to contain only ASCII characters, but {class_fault(subject, str.isascii)}", because
        )

    def is_not_ascii(self, *, because: str = "") -> Self:
        """Assert the string holds at least one character outside ASCII.

        Fails for the empty string, which ``str.isascii`` accepts.
        """
        subject = self._subject
        if not subject.isascii():
            return self
        return self._fail(
            f"not to contain only ASCII characters, but {clipped(subject)} does", because
        )

    def is_printable(self, *, because: str = "") -> Self:
        r"""Assert every character is printable (``str.isprintable``).

        Printable means: not in an "Other" Unicode category, and not a separator
        other than the ASCII space -- so ``"\n"`` and ``"\x00"`` fail where ``" "``
        passes. The other exception to the empty-string rule:
        ``"".isprintable()`` is ``True``.

        ``repr`` escapes exactly the characters this rejects, so the offender
        shows up in the message as ``'\x07'`` rather than as nothing at all.
        """
        subject = self._subject
        if subject.isprintable():
            return self
        return self._fail(
            f"to contain only printable characters, but {class_fault(subject, str.isprintable)}",
            because,
        )

    def is_not_printable(self, *, because: str = "") -> Self:
        """Assert the string holds at least one unprintable character.

        Fails for the empty string, which ``str.isprintable`` accepts.
        """
        subject = self._subject
        if not subject.isprintable():
            return self
        return self._fail(
            f"not to contain only printable characters, but {clipped(subject)} does", because
        )

    def is_space(self, *, because: str = "") -> Self:
        """Assert the string is non-empty and made only of whitespace (``str.isspace``).

        The strict sibling of :meth:`is_blank`, which also accepts the empty
        string. ``str.isspace`` does not, and the message says so.
        """
        subject = self._subject
        if subject.isspace():
            return self
        return self._fail(
            f"to contain only whitespace, but {class_fault(subject, str.isspace)}", because
        )

    def is_not_space(self, *, because: str = "") -> Self:
        """Assert the string is not made entirely of whitespace.

        Satisfied by the empty string, where :meth:`is_not_blank` is not.
        """
        subject = self._subject
        if not subject.isspace():
            return self
        return self._fail(f"not to contain only whitespace, but {clipped(subject)} does", because)
