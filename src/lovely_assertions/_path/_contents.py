"""Three assertions over a file's decoded text.

Reading is where this seam differs from every other: the file may exist and still
not be readable, and that is neither a pass nor the failure the assertion names.
The reading module answers both, and these turn the answer into a sentence.
"""

from typing import Self

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._path._purepath import DiskPath, PurePathExpect
from lovely_assertions._path._reading import read_text, read_trouble
from lovely_assertions._path._render import (
    clipped,
    invisible_note,
    missing_note,
    rendered,
    text_difference,
)

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class ContentAssertions(PurePathExpect[DiskPath]):
    """The text a file holds."""

    __slots__ = ()

    def has_text(self, expected: str, /, *, encoding: str = "utf-8", because: str = "") -> Self:
        """Assert the file's contents are exactly ``expected``.

        **Exactly** means the bytes are decoded and compared with nothing
        touched: no newline translation, no byte-order mark stripped, no
        trailing whitespace forgiven. So a CRLF file does not match LF text --
        which is the difference a Windows checkout introduces, and the one worth
        being told about. Because those differences are invisible in a rendered
        message, the failure names them: a byte-order mark, line endings, or
        surrounding whitespace each get said out loud, and anything else gets the
        library's ordinary line-by-line difference.

        The file is read as UTF-8. That is the encoding a test fixture is written
        in unless somebody decided otherwise, and ``encoding=`` is how they say
        so -- ``encoding="utf-8-sig"`` to drop a byte-order mark, ``"latin-1"``
        for bytes that must not be interpreted at all. Contents that are not text
        in that encoding fail with the codec's own reason and the offending byte
        rather than letting a ``UnicodeDecodeError`` out of an assertion; an
        encoding name that does not exist raises ``LookupError``, because that is
        a bug in the test.
        """
        subject = self._subject
        try:
            actual = read_text(subject, encoding)
        except (OSError, UnicodeDecodeError) as error:
            return self._fail(
                f"to have the text {clipped(expected)}, but {read_trouble(subject, error)}",
                because,
                cause=error,
            )
        if actual == expected:
            return self
        return self._fail(
            f"to have the text {clipped(expected)}, but {rendered(subject)} holds "
            f"{clipped(actual)}{invisible_note(actual, expected)}"
            f"{text_difference(actual, expected)}",
            because,
        )

    def contains_text(
        self, expected: str, /, *, encoding: str = "utf-8", because: str = ""
    ) -> Self:
        """Assert ``expected`` appears somewhere in the file's contents.

        A plain substring test on the decoded text, read on the same terms as
        :meth:`has_text` -- exact line endings included, so a needle spelled with
        ``\\n`` will not be found in a CRLF file, and the failure says so.
        """
        subject = self._subject
        try:
            actual = read_text(subject, encoding)
        except (OSError, UnicodeDecodeError) as error:
            return self._fail(
                f"to contain {clipped(expected)}, but {read_trouble(subject, error)}",
                because,
                cause=error,
            )
        if expected in actual:
            return self
        return self._fail(
            f"to contain {clipped(expected)}, but {rendered(subject)} holds "
            f"{clipped(actual)}{missing_note(actual, expected)}",
            because,
        )

    def does_not_contain_text(
        self, unexpected: str, /, *, encoding: str = "utf-8", because: str = ""
    ) -> Self:
        """Assert ``unexpected`` appears nowhere in the file's contents."""
        subject = self._subject
        try:
            actual = read_text(subject, encoding)
        except (OSError, UnicodeDecodeError) as error:
            return self._fail(
                f"not to contain {clipped(unexpected)}, but {read_trouble(subject, error)}",
                because,
                cause=error,
            )
        if unexpected not in actual:
            return self
        return self._fail(
            f"not to contain {clipped(unexpected)}, but {rendered(subject)} holds "
            f"{clipped(actual)}",
            because,
        )
