"""Emptiness and length: the two cheapest questions, and the ones asked most.

Empty, blank and whitespace are three different claims and a reader means one of
them. They are kept together because a test that reaches for one usually
considered the others first.
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


class SizeAssertions(Expect[str]):
    """How much text there is."""

    __slots__ = ()

    def is_empty(self, *, because: str = "") -> Self:
        """Assert the string has no characters at all."""
        if not self._subject:
            return self
        return self._fail(f"to be empty, but was {clipped(self._subject)}", because)

    def is_not_empty(self, *, because: str = "") -> Self:
        """Assert the string has at least one character."""
        if self._subject:
            return self
        return self._fail("not to be empty, but it was", because)

    def is_blank(self, *, because: str = "") -> Self:
        """Assert the string is empty or contains nothing but whitespace.

        The lenient neighbour of :meth:`is_empty`, which accepts a string of no
        characters and nothing else, and of :meth:`is_space`, which requires at
        least one whitespace character. Reach for this one when whitespace is not
        content.

        Written as ``not subject or subject.isspace()`` rather than the more
        obvious ``not subject.strip()``: same answer, without the stripped copy
        the tidier spelling allocates on every passing call, where a passing
        assertion is meant to cost a comparison and nothing more.
        """
        subject = self._subject
        if not subject or subject.isspace():
            return self
        return self._fail(f"to be blank, but was {clipped(subject)}", because)

    def is_not_blank(self, *, because: str = "") -> Self:
        """Assert the string holds something other than whitespace."""
        subject = self._subject
        if subject and not subject.isspace():
            return self
        return self._fail(f"not to be blank, but was {clipped(subject)}", because)

    # -- length ------------------------------------------------------------
    def has_length(self, expected: int, /, *, because: str = "") -> Self:
        """Assert the string is ``expected`` characters long."""
        subject = self._subject
        if len(subject) == expected:
            return self
        return self._fail(
            f"to have length {expected}, but {clipped(subject)} has length {len(subject)}",
            because,
        )
