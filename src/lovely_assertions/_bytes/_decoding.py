"""Reading a byte string as text, and continuing on what comes out.

The two questions a payload is usually asked. ``is_valid_utf8`` answers the one
before the decode, and ``decoded_as`` does the decode and hands the text on --
which is what makes this seam worth having rather than merely correct: past it
the whole string catalogue applies, to a value that really is a ``str``.

A ``UnicodeDecodeError`` carries the offset of the byte that broke, and that is
the useful half of it. Both assertions here read it out into the sentence rather
than letting the exception travel: a reader who is told "byte 3 is not valid
UTF-8" does not have to go and decode the payload themselves to find out where.
"""

from typing import TYPE_CHECKING, Self, cast

from lovely_assertions._bytes._base import BytesBase
from lovely_assertions._bytes._render import as_hex, clipped
from lovely_assertions._core import Found
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from lovely_assertions._string import StringExpect

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class DecodingAssertions(BytesBase):
    """Reading the bytes as text."""

    __slots__ = ()

    def is_valid_utf8(self, *, because: str = "") -> Self:
        """Assert the byte string decodes as UTF-8.

            expect(payload).is_valid_utf8()

        The question a reader asks before decoding, and the one whose answer is
        otherwise a ``UnicodeDecodeError`` thrown from somewhere else. The
        failure names the offset and the byte that broke, which is the half of
        that exception worth keeping:

            Expected payload to be valid UTF-8, but byte 3 (0xff) is not.

        :meth:`decoded_as` is the one to reach for when the text itself is what
        the test is about; this is for when its *validity* is.
        """
        subject = self._subject
        try:
            _ = subject.decode("utf-8")
        except UnicodeDecodeError as error:
            return self._fail(
                f"to be valid UTF-8, but byte {error.start}"
                f" ({as_hex(subject[error.start])}) is not: {clipped(subject)}",
                because,
            )
        return self

    def decoded_as(
        self, encoding: str, /, *, because: str = ""
    ) -> "Found[Self, str, StringExpect]":
        """Assert the byte string decodes, and continue on the text.

            expect(body).decoded_as("utf-8").which.starts_with("<!DOCTYPE")

        A real narrowing, not a promise: the found value is what ``bytes.decode``
        returned, so it genuinely is a ``str`` and the whole string catalogue
        follows it. ``.and_`` goes back to the bytes, ``.which`` descends into the
        text, and ``.subject`` hands the text over raw.

        Any encoding Python knows is accepted. An unknown one is a
        ``LookupError`` from the standard library, raised where it was written --
        a mistake in the test rather than a finding about the subject, and one
        this library has nothing to add to.
        """
        subject = self._subject
        try:
            text = subject.decode(encoding)
        except UnicodeDecodeError as error:
            return cast(
                "Found[Self, str, StringExpect]",
                self._fail_narrowing(
                    f"to decode as {encoding}, but byte {error.start}"
                    f" ({as_hex(subject[error.start])}) is not valid there: {clipped(subject)}",
                    because,
                ),
            )
        # No named type: `.which` dispatches the value, and a real `str` reaches
        # `StringExpect` on its own. Naming one would be a promise; this is a
        # proof, because `bytes.decode` returned the `str` two lines up.
        return Found(self, text)
